from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

import yaml
from pypdf import PdfReader

from profile_version import PROFILE_FILES, profile_version


ROOT = Path(__file__).resolve().parent.parent


def extract_resumes(files: list[Path], output_directory: Path) -> tuple[list[Path], list[str]]:
    output_directory.mkdir(parents=True, exist_ok=True)
    extracted, skipped = [], []
    for index, path in enumerate(files):
        try:
            text = "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages).strip()
        except Exception as exc:
            skipped.append(f"{path.name}: unreadable PDF ({exc})")
            continue
        if len(text) < 200:
            skipped.append(f"{path.name}: image-only or insufficient searchable text")
            continue
        target = output_directory / f"{index + 1:02d}-{path.stem}.txt"
        target.write_text(text, encoding="utf-8")
        extracted.append(target)
    return extracted, skipped


def validate_proposal(profile_directory: Path, proposal: dict, original_contact: dict) -> dict[str, dict]:
    parsed = {}
    for name in PROFILE_FILES:
        key = name.replace(".yaml", "_yaml")
        text = proposal.get(key)
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Profile rebuild did not return {name}.")
        value = yaml.safe_load(text)
        if not isinstance(value, dict):
            raise ValueError(f"{name} must contain a YAML mapping.")
        parsed[name] = value
    if parsed["career.yaml"].get("contact") != original_contact:
        raise ValueError("Profile rebuild attempted to change the protected contact section.")
    evidence = parsed["evidence.yaml"].get("evidence", [])
    evidence_ids = {item.get("id") for item in evidence if isinstance(item, dict)}
    if None in evidence_ids or len(evidence_ids) != len(evidence):
        raise ValueError("Every evidence item must have a unique ID.")
    missing: set[str] = set()
    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "evidence_ids" and isinstance(item, list):
                    missing.update(ref for ref in item if isinstance(ref, str) and ref not in evidence_ids)
                visit(item)
        elif isinstance(value, list):
            for item in value: visit(item)
    for name in ("career.yaml", "skills.yaml", "technologies.yaml"):
        visit(parsed[name])
    if missing:
        raise ValueError("Unknown evidence IDs in rebuilt profile: " + ", ".join(sorted(missing)))
    return parsed


def codex_proposal(extracted_directory: Path, instructions: str) -> dict:
    schema = {
        "type": "object",
        "properties": {
            **{name.replace(".yaml", "_yaml"): {"type": "string"} for name in PROFILE_FILES},
            "changes": {"type": "array", "items": {"type": "string"}},
            "review_items": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["Experience", "Skills", "Technologies", "Evidence", "Profile guidance"]},
                    "action": {"type": "string", "enum": ["Added", "Updated", "Removed"]},
                    "fact": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["category", "action", "fact", "reason"],
                "additionalProperties": False,
            }},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": [*(name.replace(".yaml", "_yaml") for name in PROFILE_FILES), "changes", "review_items", "warnings"],
        "additionalProperties": False,
    }
    prompt = f"""
Rebuild the verified career profile from the existing profile/*.yaml files and every
resume text file in {extracted_directory.relative_to(ROOT)}. Follow AGENTS.md.
Return complete YAML text for career.yaml, skills.yaml, technologies.yaml, and evidence.yaml.
Preserve the existing career.contact mapping exactly. Never invent or exaggerate facts.
Reconcile conflicts conservatively, preserve credibility/prohibited-exaggeration notes,
deduplicate facts, and use conservative proficiency labels. Do not modify files.
Provide review_items as concise, plain-language facts for a non-technical user. Describe
what was added, updated, or removed and why the uploaded resumes support that change.
Do not mention YAML, field names, evidence IDs, schemas, or internal file structure in review_items.
Additional user instructions: {instructions or 'None provided.'}
""".strip()
    executable = os.environ.get("CODEX_EXECUTABLE", "/Applications/ChatGPT.app/Contents/Resources/codex")
    model = os.environ.get("PROFILE_REBUILD_MODEL", "gpt-5.6-sol")
    with tempfile.TemporaryDirectory() as directory:
        schema_path = Path(directory) / "schema.json"; result_path = Path(directory) / "result.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        subprocess.run([
            executable, "exec", "--ephemeral", "--sandbox", "read-only", "--model", model,
            "--cd", str(ROOT), "--output-schema", str(schema_path),
            "--output-last-message", str(result_path), prompt,
        ], cwd=ROOT, check=True, capture_output=True, text=True)
        return json.loads(result_path.read_text(encoding="utf-8"))


def prepare_profile_rebuild(run_id: str, files: list[Path], instructions: str, generator: Callable[[Path, str], dict] = codex_proposal) -> dict:
    run_directory = ROOT / "data/profile-rebuilds" / run_id
    extracted, skipped = extract_resumes(files, run_directory / "extracted")
    if files and not extracted:
        raise ValueError("None of the uploaded PDFs contained enough searchable resume text.")
    profile_directory = ROOT / "profile"
    original_contact = yaml.safe_load((profile_directory / "career.yaml").read_text())["contact"]
    proposal = generator(run_directory / "extracted", instructions)
    parsed = validate_proposal(profile_directory, proposal, original_contact)
    changed_sections = []
    section_labels = {"career.yaml": "Experience", "skills.yaml": "Skills", "technologies.yaml": "Technologies", "evidence.yaml": "Supporting evidence"}
    for name in PROFILE_FILES:
        staged = run_directory / name
        staged.write_text(yaml.safe_dump(parsed[name], sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
        current_value = yaml.safe_load((profile_directory / name).read_text(encoding="utf-8"))
        if current_value != parsed[name]:
            changed_sections.append(section_labels[name])
    return {
        "files_processed": [path.name for path in extracted],
        "files_skipped": skipped,
        "changes": proposal.get("changes", []),
        "review_items": proposal.get("review_items", []),
        "warnings": proposal.get("warnings", []),
        "changed_sections": changed_sections,
    }


def apply_profile_rebuild(run_id: str, expected_version: str) -> dict:
    run_directory = ROOT / "data/profile-rebuilds" / run_id
    profile_directory = ROOT / "profile"
    if profile_version(profile_directory) != expected_version:
        raise ValueError("The career profile changed while this proposal was waiting. Rebuild the proposal before approving it.")
    for name in PROFILE_FILES:
        if not (run_directory / name).exists():
            raise ValueError(f"The proposed {name} file is missing.")
    backup = ROOT / "profile/history" / run_id; backup.mkdir(parents=True, exist_ok=True)
    for name in PROFILE_FILES:
        shutil.copy2(profile_directory / name, backup / name)
    try:
        for name in PROFILE_FILES:
            shutil.copy2(run_directory / name, profile_directory / name)
    except OSError:
        for name in PROFILE_FILES:
            shutil.copy2(backup / name, profile_directory / name)
        raise
    return {
        "profile_version": profile_version(profile_directory),
        "backup": str(backup.relative_to(ROOT)),
    }

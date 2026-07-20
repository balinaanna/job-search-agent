#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from analyze_job_with_codex import strict_output_schema
from validate_job_lead import load_json
from write_cover_letter_with_codex import normalize_trace, word_count
from write_resume_with_codex import find_workspace

ROOT = Path(__file__).resolve().parent.parent
REVISION_SCHEMA = ROOT / "hermes-skills/cover-letter-reviser/references/cover-letter-revision-schema.json"
REVIEW_SCHEMA = ROOT / "hermes-skills/cover-letter-reviewer/references/cover-letter-review-schema.json"
TRACE_SCHEMA = ROOT / "hermes-skills/cover-letter-writer/references/cover-letter-trace-schema.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def next_version(workspace: Path) -> int:
    versions = workspace / "versions"
    number = 1
    while (versions / f"cover_letter_v{number}.md").exists():
        number += 1
    return number


def create_snapshots(workspace: Path, version: int) -> list[dict]:
    versions = workspace / "versions"
    versions.mkdir(exist_ok=True)
    items = [
        ("cover_letter", workspace / "cover_letter.md", versions / f"cover_letter_v{version}.md"),
        ("cover_letter_trace", workspace / "cover_letter_trace.json", versions / f"cover_letter_trace_v{version}.json"),
        ("cover_letter_review_json", workspace / "cover_letter_review.json", versions / f"cover_letter_review_v{version}.json"),
        ("cover_letter_review_markdown", workspace / "cover_letter_review.md", versions / f"cover_letter_review_v{version}.md"),
    ]
    snapshots = []
    for artifact_type, source, target in items:
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite revision snapshot: {target}")
        shutil.copy2(source, target)
        snapshots.append({"artifact_type": artifact_type, "path": str(target.relative_to(workspace)), "sha256": sha256(target)})
    return snapshots


def output_schema() -> dict:
    trace = {key: value for key, value in load_json(TRACE_SCHEMA).items() if key != "$schema"}
    revision = {key: value for key, value in load_json(REVISION_SCHEMA).items() if key != "$schema"}
    return strict_output_schema({
        "type": "object",
        "properties": {"letter_markdown": {"type": "string"}, "trace": trace, "revision": revision},
        "required": ["letter_markdown", "trace", "revision"], "additionalProperties": False,
    })


def normalize_revision(revision: dict, review: dict, before_trace: dict, after_trace: dict, before_letter: str, after_letter: str, snapshots: list[dict], version: int, workspace: Path) -> None:
    brief = review["revision_brief"]
    before = {item["paragraph_id"]: item for item in before_trace["paragraphs"]}
    after = {item["paragraph_id"]: item for item in after_trace["paragraphs"]}
    changed_ids = [pid for pid in before if before[pid]["text"] != after[pid]["text"]]
    unauthorized = set(changed_ids) - set(brief["authorized_paragraph_ids"])
    if unauthorized:
        raise ValueError("Unauthorized cover letter paragraphs changed: " + ", ".join(sorted(unauthorized)))
    if not changed_ids:
        raise ValueError("The revision did not change any authorized paragraph.")
    supplied_changes = {item["paragraph_id"]: item for item in revision["paragraph_changes"]}
    findings = {item["finding_id"]: item for item in review["findings"]}
    revision["application_id"] = review["application_id"]
    revision["source_review"] = {"score": review["score"], "verdict": review["verdict"], "review_path": str((workspace / "cover_letter_review.json").relative_to(ROOT))}
    revision["version"] = version
    revision["snapshots"] = snapshots
    revision["authorized_paragraph_ids"] = brief["authorized_paragraph_ids"]
    supplied_processed = {item["finding_id"]: item for item in revision["processed_findings"]}
    revision["processed_findings"] = []
    for finding_id in brief["priority_order"]:
        finding = findings[finding_id]
        supplied = supplied_processed.get(finding_id, {})
        revision["processed_findings"].append({
            "finding_id": finding_id, "paragraph_id": finding["paragraph_id"],
            "status": supplied.get("status", "not_resolved"),
            "revision_instruction": finding["revision_instruction"],
            "resolution_summary": supplied.get("resolution_summary", "The authorized instruction could not be applied safely."),
        })
    revision["paragraph_changes"] = []
    for pid in changed_ids:
        supplied = supplied_changes.get(pid, {})
        finding_ids = [fid for fid in brief["priority_order"] if findings[fid]["paragraph_id"] == pid]
        revision["paragraph_changes"].append({
            "paragraph_id": pid, "finding_ids": finding_ids,
            "before_text": before[pid]["text"], "after_text": after[pid]["text"],
            "change_summary": supplied.get("change_summary", "Applied the authorized review instructions."),
            "evidence_ids_before": before[pid]["evidence_ids"], "evidence_ids_after": after[pid]["evidence_ids"],
            "resume_element_ids_before": before[pid]["resume_element_ids"], "resume_element_ids_after": after[pid]["resume_element_ids"],
            "word_count_before": word_count(before[pid]["text"]), "word_count_after": word_count(after[pid]["text"]),
        })
    revision["unchanged_paragraph_ids"] = [pid for pid in before if pid not in changed_ids]
    plan = load_json(workspace / "cover_letter_plan.json")
    revision["word_counts"] = {
        "before": word_count(before_letter), "after": word_count(after_letter),
        "target_min": plan["structure"]["target_words_min"], "target_max": plan["structure"]["target_words_max"], "within_range": True,
    }
    revision["manifest_status"] = "cover_letter_revision"


def render_revision(revision: dict) -> str:
    lines = ["# Cover letter revision", "", f"Version snapshot: v{revision['version']}", "", "## Findings addressed", ""]
    lines.extend([f"- {item['finding_id']}: {item['status'].replace('_', ' ')} - {item['resolution_summary']}" for item in revision["processed_findings"]])
    lines.extend(["", "## Paragraph changes", ""])
    lines.extend([f"- {item['paragraph_id']}: {item['change_summary']}" for item in revision["paragraph_changes"]])
    lines.extend(["", "## Next step", "", "Run the recruiter-style review again before approval.", ""])
    return "\n".join(lines)


def revise_cover_letter(lead_id: str, notes: str, codex: str, model: str) -> Path:
    workspace = find_workspace(lead_id)
    manifest_path = workspace / "application_manifest.json"
    manifest = load_json(manifest_path)
    review = load_json(workspace / "cover_letter_review.json")
    if manifest.get("status") != "cover_letter_review" or review.get("verdict") == "ready":
        raise ValueError("Only a non-ready reviewed cover letter can enter revision.")
    if not review.get("revision_brief", {}).get("authorized_paragraph_ids"):
        raise ValueError("The review did not authorize any paragraphs for revision.")
    subprocess.run([os.sys.executable, "scripts/validate_cover_letter_review.py", str(workspace), "--schema", str(REVIEW_SCHEMA)], cwd=ROOT, check=True)
    plan = load_json(workspace / "cover_letter_plan.json")
    before_letter = (workspace / "cover_letter.md").read_text(encoding="utf-8")
    before_trace = load_json(workspace / "cover_letter_trace.json")
    version = next_version(workspace)
    snapshots = create_snapshots(workspace, version)
    prompt = f"""
Revise the cover letter using the complete hermes-skills/cover-letter-reviser/SKILL.md workflow.
Use only {workspace.relative_to(ROOT)}, the review's authorized findings, and verified evidence.
The user's notes are {json.dumps(notes)}. Apply them only within authorized paragraphs and findings;
otherwise preserve the approved review scope. Make the smallest sufficient changes. Do not browse,
replan, re-review, finalize, or render. Return letter_markdown, a complete trace, and revision record.
Use version {version}, snapshots {json.dumps(snapshots)}, and manifest_status cover_letter_revision.
""".strip()
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "cover-letter-revision.json"
        schema = Path(directory) / "schema.json"
        schema.write_text(json.dumps(output_schema()), encoding="utf-8")
        subprocess.run(
            [codex, "exec", "--ephemeral", "--sandbox", "read-only", "--model", model,
             "--cd", str(ROOT), "--output-schema", str(schema), "--output-last-message", str(output), prompt],
            cwd=ROOT, check=True,
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
    letter = payload["letter_markdown"].strip() + "\n"
    trace = payload["trace"]
    normalize_trace(trace, letter, plan, workspace)
    revision = payload["revision"]
    normalize_revision(revision, review, before_trace, trace, before_letter, letter, snapshots, version, workspace)
    (workspace / "cover_letter.md").write_text(letter, encoding="utf-8")
    (workspace / "cover_letter_trace.json").write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
    revision_path = workspace / "cover_letter_revision.json"
    revision_path.write_text(json.dumps(revision, indent=2) + "\n", encoding="utf-8")
    (workspace / "cover_letter_revision.md").write_text(render_revision(revision), encoding="utf-8")
    manifest["status"] = "cover_letter_revision"
    manifest.setdefault("artifacts", {}).update({
        "cover_letter_revision_json": str(revision_path.relative_to(ROOT)),
        "cover_letter_revision_markdown": str((workspace / "cover_letter_revision.md").relative_to(ROOT)),
    })
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    subprocess.run([os.sys.executable, "scripts/validate_cover_letter_revision.py", str(workspace), "--schema", str(REVISION_SCHEMA)], cwd=ROOT, check=True)
    return revision_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lead_id")
    parser.add_argument("--notes", required=True)
    parser.add_argument("--codex", default=os.environ.get("CODEX_EXECUTABLE", "/Applications/ChatGPT.app/Contents/Resources/codex"))
    parser.add_argument("--model", default=os.environ.get("COVER_LETTER_REVISION_MODEL", "gpt-5.6-sol"))
    args = parser.parse_args()
    print(revise_cover_letter(args.lead_id, args.notes, args.codex, args.model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

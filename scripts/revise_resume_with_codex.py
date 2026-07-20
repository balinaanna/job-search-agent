#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from analyze_job_with_codex import strict_output_schema
from validate_job_lead import load_json
from write_resume_with_codex import find_workspace, normalize_trace

ROOT = Path(__file__).resolve().parent.parent
REVISION_SCHEMA = ROOT / "hermes-skills/resume-reviser/references/resume-revision-schema.json"
REVIEW_SCHEMA = ROOT / "hermes-skills/resume-reviewer/references/resume-review-schema.json"
TRACE_SCHEMA = ROOT / "hermes-skills/resume-writer/references/resume-trace-schema.json"


def next_revision(workspace: Path) -> int:
    versions = workspace / "versions"
    numbers = []
    for path in versions.glob("resume_v*.md") if versions.exists() else []:
        match = re.fullmatch(r"resume_v(\d+)\.md", path.name)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def backup_files(workspace: Path, number: int) -> dict[str, str]:
    versions = workspace / "versions"
    versions.mkdir(exist_ok=True)
    names = {
        "resume": (workspace / "resume.md", versions / f"resume_v{number}.md"),
        "trace": (workspace / "resume_trace.json", versions / f"resume_trace_v{number}.json"),
        "review_json": (workspace / "resume_review.json", versions / f"resume_review_v{number}.json"),
        "review_markdown": (workspace / "resume_review.md", versions / f"resume_review_v{number}.md"),
    }
    for source, target in names.values():
        if target.exists():
            raise FileExistsError(f"Revision backup already exists: {target}")
        shutil.copy2(source, target)
    return {key: str(target) for key, (_, target) in names.items()}


def envelope_schema() -> dict:
    trace = {key: value for key, value in load_json(TRACE_SCHEMA).items() if key != "$schema"}
    revision = {key: value for key, value in load_json(REVISION_SCHEMA).items() if key != "$schema"}
    return strict_output_schema({
        "type": "object",
        "properties": {
            "resume_markdown": {"type": "string"},
            "trace": trace,
            "revision": revision,
        },
        "required": ["resume_markdown", "trace", "revision"],
        "additionalProperties": False,
    })


def render_revision(revision: dict) -> str:
    lines = [
        f"# Resume revision {revision['revision_number']}", "", "## Changes applied", "",
    ]
    changed = [item for item in revision["changed_elements"] if item["change_type"] != "unchanged_preserved"]
    lines.extend([f"- {item['element_id']}: {item['change_type'].replace('_', ' ')}" for item in changed] or ["- No text changes were safe or necessary."])
    lines.extend(["", "## Findings disposition", ""])
    lines.extend([f"- **{item['finding_id']} — {item['status'].replace('_', ' ')}:** {item['reason']}" for item in revision["findings_disposition"]])
    lines.extend(["", "## Unresolved conflicts", ""])
    lines.extend([f"- {item['instruction']}: {item['resolution']}" for item in revision["unresolved_conflicts"]] or ["- None."])
    lines.extend(["", "## Next step", "", "Run the recruiter-style review again before approval.", ""])
    return "\n".join(lines)


def revise_resume(lead_id: str, notes: str, codex: str, model: str) -> Path:
    workspace = find_workspace(lead_id)
    manifest_path = workspace / "application_manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("status") != "review":
        raise ValueError("The resume must have a completed review before revision.")
    subprocess.run(
        [os.sys.executable, "scripts/validate_resume_review.py", str(workspace), "--schema", str(REVIEW_SCHEMA)],
        cwd=ROOT, check=True,
    )
    subprocess.run(
        [os.sys.executable, "scripts/validate_resume_draft.py", str(workspace), "--schema", str(TRACE_SCHEMA), "--expected-status", "review"],
        cwd=ROOT, check=True,
    )
    plan = load_json(workspace / "resume_plan.json")
    review = load_json(workspace / "resume_review.json")
    number = next_revision(workspace)
    backups = backup_files(workspace, number)
    prompt = f"""
Revise the resume using the complete hermes-skills/resume-reviser/SKILL.md workflow.
Work only from {workspace.relative_to(ROOT)}, its approved review brief, and verified profile evidence.
The user's additional revision notes are: {json.dumps(notes)}
Treat those notes as authorized only where consistent with the plan and evidence; record conflicts instead
of inventing or expanding claims. Do not browse, redesign the strategy, finalize, or submit.
Return resume_markdown, a complete replacement trace, and the revision record.
Use revision_number {number}, source_review_path {workspace / 'resume_review.json'},
backup_paths {json.dumps(backups)}, output resume path {workspace / 'resume.md'}, output trace path
{workspace / 'resume_trace.json'}, revision Markdown path {workspace / 'resume_revision.md'},
application_id {manifest['application_id']}, and manifest_status drafting.
""".strip()
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "revision-result.json"
        schema = Path(directory) / "revision-schema.json"
        schema.write_text(json.dumps(envelope_schema()), encoding="utf-8")
        subprocess.run(
            [codex, "exec", "--ephemeral", "--sandbox", "read-only", "--model", model,
             "--cd", str(ROOT), "--output-schema", str(schema),
             "--output-last-message", str(output), prompt], cwd=ROOT, check=True,
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
    resume = payload["resume_markdown"].strip() + "\n"
    trace = payload["trace"]
    revision = payload["revision"]
    normalize_trace(trace, resume, plan)
    revision["revision_number"] = number
    revision["source_review_path"] = str(workspace / "resume_review.json")
    revision["backup_paths"] = backups
    revision["output_paths"] = {
        "resume": str(workspace / "resume.md"),
        "trace": str(workspace / "resume_trace.json"),
        "revision_markdown": str(workspace / "resume_revision.md"),
    }
    revision["word_counts"] = {
        "before": len(re.findall(r"\b[\w’'-]+\b", Path(backups["resume"]).read_text(encoding="utf-8"))),
        "after": len(re.findall(r"\b[\w’'-]+\b", resume)),
    }
    revision["manifest_status"] = "drafting"
    (workspace / "resume.md").write_text(resume, encoding="utf-8")
    (workspace / "resume_trace.json").write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
    revision_path = workspace / "resume_revision.json"
    revision_path.write_text(json.dumps(revision, indent=2) + "\n", encoding="utf-8")
    (workspace / "resume_revision.md").write_text(render_revision(revision), encoding="utf-8")
    manifest["status"] = "drafting"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    subprocess.run(
        [os.sys.executable, "scripts/validate_resume_draft.py", str(workspace), "--schema", str(TRACE_SCHEMA)],
        cwd=ROOT, check=True,
    )
    subprocess.run(
        [os.sys.executable, "scripts/validate_resume_revision.py", str(workspace), "--schema", str(REVISION_SCHEMA)],
        cwd=ROOT, check=True,
    )
    return revision_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lead_id")
    parser.add_argument("--notes", required=True)
    parser.add_argument("--codex", default=os.environ.get("CODEX_EXECUTABLE", "/Applications/ChatGPT.app/Contents/Resources/codex"))
    parser.add_argument("--model", default=os.environ.get("RESUME_REVISION_MODEL", "gpt-5.6-sol"))
    args = parser.parse_args()
    print(revise_resume(args.lead_id, args.notes, args.codex, args.model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

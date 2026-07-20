#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from analyze_job_with_codex import strict_output_schema
from validate_job_lead import load_json
from write_resume_with_codex import find_workspace

ROOT = Path(__file__).resolve().parent.parent
REVIEW_SCHEMA = ROOT / "hermes-skills/cover-letter-reviewer/references/cover-letter-review-schema.json"
TRACE_SCHEMA = ROOT / "hermes-skills/cover-letter-writer/references/cover-letter-trace-schema.json"


def reduce_score(breakdown: dict, target: int) -> None:
    excess = sum(breakdown.values()) - target
    for key in reversed(list(breakdown)):
        reduction = min(excess, breakdown[key])
        breakdown[key] -= reduction
        excess -= reduction
        if not excess:
            break


def normalize_review(review: dict, application_id: str) -> None:
    review["application_id"] = application_id
    breakdown = review["score_breakdown"]
    severities = {item["severity"] for item in review["findings"]}
    total = sum(breakdown.values())
    if "critical" in severities and total >= 80:
        reduce_score(breakdown, 79)
    elif "high" in severities and total >= 90:
        reduce_score(breakdown, 89)
    total = sum(breakdown.values())
    review["score"] = total
    review["verdict"] = "ready" if total >= 90 else "minor_revision" if total >= 80 else "major_revision" if total >= 65 else "rewrite_required"
    review["manifest_status"] = "cover_letter_review"
    if review["verdict"] == "ready":
        review["revision_brief"]["authorized_paragraph_ids"] = []
        review["revision_brief"]["priority_order"] = []


def render_review(review: dict) -> str:
    lines = [
        "# Cover letter review", "", f"**{review['score']}/100 - {review['verdict'].replace('_', ' ').title()}**", "",
        "## Recruiter first impression", "", review["first_impression"]["summary"], "", "## Strengths", "",
    ]
    lines.extend([f"- {item['description']}" for item in review["strengths"]])
    lines.extend(["", "## Findings", ""])
    if review["findings"]:
        for item in review["findings"]:
            lines.extend([
                f"### {item['finding_id']} - {item['severity'].title()} - {item['paragraph_id']}", "",
                item["issue"], "", f"**Impact:** {item['impact']}", "",
                f"**Revision instruction:** {item['revision_instruction']}", "",
            ])
    else:
        lines.extend(["No findings.", ""])
    lines.extend(["## Next step", "", "Approve the ready letter or authorize a bounded revision.", ""])
    return "\n".join(lines)


def review_cover_letter(lead_id: str, codex: str, model: str) -> Path:
    workspace = find_workspace(lead_id)
    manifest_path = workspace / "application_manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("status") != "cover_letter_drafting":
        raise ValueError("A validated cover letter draft is required before review.")
    subprocess.run(
        [os.sys.executable, "scripts/validate_cover_letter_draft.py", str(workspace), "--schema", str(TRACE_SCHEMA)],
        cwd=ROOT, check=True,
    )
    prompt = f"""
Review the cover letter using the complete hermes-skills/cover-letter-reviewer/SKILL.md workflow.
Use only {workspace.relative_to(ROOT)}, its recorded job analysis, and verified profile evidence.
Do not browse, rewrite, revise, or provide replacement sentences. Return only schema-conforming JSON.
Use application_id {manifest['application_id']} and manifest_status cover_letter_review.
Make every finding paragraph-specific, concrete, and bounded by the approved evidence.
""".strip()
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "cover-letter-review.json"
        schema = Path(directory) / "schema.json"
        schema.write_text(json.dumps(strict_output_schema(load_json(REVIEW_SCHEMA))), encoding="utf-8")
        subprocess.run(
            [codex, "exec", "--ephemeral", "--sandbox", "read-only", "--model", model,
             "--cd", str(ROOT), "--output-schema", str(schema),
             "--output-last-message", str(output), prompt], cwd=ROOT, check=True,
        )
        review = json.loads(output.read_text(encoding="utf-8"))
    normalize_review(review, manifest["application_id"])
    review_path = workspace / "cover_letter_review.json"
    review_path.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    (workspace / "cover_letter_review.md").write_text(render_review(review), encoding="utf-8")
    manifest["status"] = "cover_letter_review"
    artifacts = manifest.setdefault("artifacts", {})
    artifacts.update({
        "cover_letter_review_json": str(review_path.relative_to(ROOT)),
        "cover_letter_review_markdown": str((workspace / "cover_letter_review.md").relative_to(ROOT)),
    })
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    subprocess.run(
        [os.sys.executable, "scripts/validate_cover_letter_review.py", str(workspace), "--schema", str(REVIEW_SCHEMA)],
        cwd=ROOT, check=True,
    )
    return review_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lead_id")
    parser.add_argument("--codex", default=os.environ.get("CODEX_EXECUTABLE", "/Applications/ChatGPT.app/Contents/Resources/codex"))
    parser.add_argument("--model", default=os.environ.get("COVER_LETTER_REVIEW_MODEL", "gpt-5.6-sol"))
    args = parser.parse_args()
    print(review_cover_letter(args.lead_id, args.codex, args.model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

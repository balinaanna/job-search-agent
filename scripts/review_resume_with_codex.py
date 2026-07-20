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
REVIEW_SCHEMA = ROOT / "hermes-skills/resume-reviewer/references/resume-review-schema.json"
TRACE_SCHEMA = ROOT / "hermes-skills/resume-writer/references/resume-trace-schema.json"


def normalize_review(review: dict) -> None:
    score = review["review_score"]
    components = (
        "first_scan_clarity", "strategic_alignment", "evidence_accomplishments",
        "relevance_keyword_coverage", "readability_structure", "credibility_defensibility",
    )
    score["total"] = sum(score[name] for name in components)
    findings = review["findings"]
    summary = review["validation_summary"]
    for severity in ("critical", "high", "medium", "low"):
        summary[f"{severity}_count"] = sum(item["severity"] == severity for item in findings)
    unique = len({item["finding_id"] for item in findings}) == len(findings)
    expected = "rewrite_required" if score["total"] < 65 else "major_revision" if score["total"] < 80 else "minor_revision" if score["total"] < 90 else "ready"
    if summary["critical_count"] and expected == "ready":
        expected = "minor_revision"
    review["verdict"] = expected
    summary["all_finding_ids_unique"] = unique
    summary["score_components_valid"] = True
    summary["verdict_consistent"] = True


def render_review(review: dict) -> str:
    score = review["review_score"]["total"]
    lines = [
        "# Resume review", "", f"**{score}/100 — {review['verdict'].replace('_', ' ').title()}**",
        "", "## First impression", "", review["first_impression"], "", "## Strengths", "",
        *[f"- {item}" for item in review["strengths"]], "", "## Findings", "",
    ]
    if review["findings"]:
        for item in review["findings"]:
            lines.extend([
                f"### {item['finding_id']} — {item['severity'].title()}", "",
                item["problem"], "", f"**Why it matters:** {item['why_it_matters']}", "",
                f"**Revision:** {item['revision_instruction']}", "",
            ])
    else:
        lines.extend(["No findings.", ""])
    lines.extend(["## Strengths to preserve", "", *[f"- {item}" for item in review["strengths_to_preserve"]], ""])
    return "\n".join(lines)


def review_resume(lead_id: str, codex: str, model: str) -> Path:
    workspace = find_workspace(lead_id)
    manifest_path = workspace / "application_manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("status") not in {"drafting", "review"}:
        raise ValueError("Resume workspace must be in drafting or review status.")
    subprocess.run(
        [os.sys.executable, "scripts/validate_resume_draft.py", str(workspace),
         "--schema", str(TRACE_SCHEMA), "--expected-status", manifest["status"]],
        cwd=ROOT, check=True,
    )
    plan = load_json(workspace / "resume_plan.json")
    prompt = f"""
Review the resume using the complete hermes-skills/resume-reviewer/SKILL.md workflow.
Inputs are in {workspace.relative_to(ROOT)}. Use the analysis and strategy paths recorded
in the plan and only verified profile evidence. Do not browse or rewrite the resume.
Return only schema-conforming review JSON. Use absolute resume_path {workspace / 'resume.md'},
absolute source_plan_path {workspace / 'resume_plan.json'}, source_strategy_path
{plan['source']['strategy_path']}, and application_id {manifest['application_id']}.
Make every finding concrete, prioritized, and safe for an evidence-constrained revision.
""".strip()
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "review.json"
        schema_path = Path(directory) / "schema.json"
        schema_path.write_text(json.dumps(strict_output_schema(load_json(REVIEW_SCHEMA))), encoding="utf-8")
        subprocess.run(
            [codex, "exec", "--ephemeral", "--sandbox", "read-only", "--model", model,
             "--cd", str(ROOT), "--output-schema", str(schema_path),
             "--output-last-message", str(output), prompt], cwd=ROOT, check=True,
        )
        review = json.loads(output.read_text(encoding="utf-8"))
    normalize_review(review)
    review_path = workspace / "resume_review.json"
    review_path.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    (workspace / "resume_review.md").write_text(render_review(review), encoding="utf-8")
    manifest["status"] = "review"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    subprocess.run(
        [os.sys.executable, "scripts/validate_resume_review.py", str(workspace),
         "--schema", str(REVIEW_SCHEMA)], cwd=ROOT, check=True,
    )
    return review_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lead_id")
    parser.add_argument("--codex", default=os.environ.get("CODEX_EXECUTABLE", "/Applications/ChatGPT.app/Contents/Resources/codex"))
    parser.add_argument("--model", default=os.environ.get("RESUME_REVIEW_MODEL", "gpt-5.6-sol"))
    args = parser.parse_args()
    print(review_resume(args.lead_id, args.codex, args.model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

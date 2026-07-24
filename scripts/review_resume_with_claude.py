#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from analyze_job_with_codex import strict_output_schema
from review_resume_with_codex import REVIEW_SCHEMA, TRACE_SCHEMA, normalize_review, render_review
from validate_job_lead import load_json
from write_resume_with_codex import find_workspace


ROOT = Path(__file__).resolve().parent.parent


def review_resume(lead_id: str, claude: str, model: str) -> Path:
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
    strict_schema = strict_output_schema(load_json(REVIEW_SCHEMA))
    strict_schema.pop("$schema", None)
    schema = json.dumps(strict_schema)
    completed = subprocess.run(
        [
            claude,
            "--print",
            "--output-format",
            "json",
            "--model",
            model,
            "--tools",
            "Read,Grep,Glob",
            "--permission-mode",
            "bypassPermissions",
            "--no-session-persistence",
            "--json-schema",
            schema,
            prompt,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[-2000:]
        raise RuntimeError(f"claude CLI exited with status {completed.returncode}: {detail}")
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"claude CLI did not return valid JSON: {completed.stdout.strip()[-2000:]}"
        ) from exc
    if response.get("is_error"):
        raise RuntimeError(response.get("result", "Claude Code resume review failed."))
    review = json.loads(response["result"])
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
    parser.add_argument("--claude", default=os.environ.get("CLAUDE_EXECUTABLE", "claude"))
    parser.add_argument("--model", default=os.environ.get("CLAUDE_RESUME_REVIEW_MODEL", "sonnet"))
    args = parser.parse_args()
    print(review_resume(args.lead_id, args.claude, args.model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

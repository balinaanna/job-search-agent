#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from analyze_job_with_codex import strict_output_schema
from build_strategy_with_codex import find_analysis
from build_resume_plan_with_codex import (
    MANIFEST_SCHEMA,
    PLAN_SCHEMA,
    create_manifest,
    render_plan,
    slug,
)
from validate_job_lead import load_json


ROOT = Path(__file__).resolve().parent.parent


def build_resume_plan(lead_id: str, claude: str, model: str) -> Path:
    analysis_path = find_analysis(lead_id)
    strategy_path = analysis_path.parent / "candidate_strategy.json"
    if not strategy_path.exists():
        raise FileNotFoundError("Validated candidate strategy is required.")
    strategy = load_json(strategy_path)
    workspace = ROOT / "applications" / slug(f"{strategy['job']['company']}-{strategy['job']['title']}")
    workspace.mkdir(parents=True, exist_ok=True)
    manifest_path = workspace / "application_manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else create_manifest(analysis_path, strategy_path, workspace)
    if manifest.get("submission", {}).get("submitted") is True:
        raise ValueError("A submitted application workspace cannot be overwritten.")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    prompt = f"""
Create a resume plan using hermes-skills/resume-planner/SKILL.md from
{analysis_path.relative_to(ROOT)} and {strategy_path.relative_to(ROOT)}.
Follow AGENTS.md and all verified profile records. Do not browse or draft resume prose.
For every technical, AI, software engineering, systems analysis, business analysis, product,
implementation, or technical project role, include the current ai_job_search_agent project in
the plan. Select only the job-relevant verified evidence from ev_job_agent_product_analysis,
ev_job_agent_full_stack_delivery, ev_job_agent_ai_workflows, and
ev_job_agent_safety_and_quality; do not force every aspect into one resume.
Return only schema-conforming JSON. Use application_id {manifest['application_id']},
application_slug {manifest['application_slug']}, workspace_path {workspace.relative_to(ROOT)},
and mode {'practice_only' if manifest['fit']['recommendation'] == 'do_not_apply' else 'active_application'}.
""".strip()
    strict_schema = strict_output_schema(load_json(PLAN_SCHEMA))
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
        raise RuntimeError(response.get("result", "Claude Code resume planning failed."))
    plan = json.loads(response["result"])
    plan_path = workspace / "resume_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    (workspace / "resume_plan.md").write_text(render_plan(plan), encoding="utf-8")
    subprocess.run(
        [os.sys.executable, "scripts/validate_resume_plan.py", str(workspace),
         "--resume-schema", str(PLAN_SCHEMA), "--manifest-schema", str(MANIFEST_SCHEMA)],
        cwd=ROOT, check=True,
    )
    return plan_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lead_id")
    parser.add_argument("--claude", default=os.environ.get("CLAUDE_EXECUTABLE", "claude"))
    parser.add_argument("--model", default=os.environ.get("CLAUDE_RESUME_PLAN_MODEL", "sonnet"))
    args = parser.parse_args()
    print(build_resume_plan(args.lead_id, args.claude, args.model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

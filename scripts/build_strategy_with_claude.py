#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from analyze_job_with_codex import strict_output_schema
from build_strategy_with_codex import SCHEMA_PATH, find_analysis, render_markdown
from validate_job_lead import load_json


ROOT = Path(__file__).resolve().parent.parent


def build_strategy(lead_id: str, claude: str, model: str) -> Path:
    analysis_path = find_analysis(lead_id)
    prompt = f"""
Build the candidate strategy from {analysis_path.relative_to(ROOT)} using the complete
hermes-skills/candidate-strategy/SKILL.md workflow and verified profile files.
Follow AGENTS.md. Preserve the analysis score and recommendation. Do not browse,
write application documents, or invent facts. Return only schema-conforming JSON.
Set job.exploration_slug to {analysis_path.parent.name} and source_analysis.analysis_path
to {analysis_path.relative_to(ROOT)}.
""".strip()
    strict_schema = strict_output_schema(load_json(SCHEMA_PATH))
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
        raise RuntimeError(response.get("result", "Claude Code strategy generation failed."))
    strategy = json.loads(response["result"])
    output = analysis_path.parent / "candidate_strategy.json"
    output.write_text(json.dumps(strategy, indent=2) + "\n", encoding="utf-8")
    validation = subprocess.run(
        [os.sys.executable, "scripts/validate_candidate_strategy.py", str(output),
         "--schema", str(SCHEMA_PATH)], cwd=ROOT, capture_output=True, text=True,
    )
    if validation.returncode:
        details = (validation.stdout or validation.stderr).strip()
        raise ValueError(details or "Generated strategy did not pass validation.")
    (analysis_path.parent / "candidate_strategy.md").write_text(
        render_markdown(strategy), encoding="utf-8"
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lead_id")
    parser.add_argument("--claude", default=os.environ.get("CLAUDE_EXECUTABLE", "claude"))
    parser.add_argument("--model", default=os.environ.get("CLAUDE_STRATEGY_MODEL", "sonnet"))
    args = parser.parse_args()
    try:
        print(build_strategy(args.lead_id, args.claude, args.model))
        return 0
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"Strategy could not be prepared: {exc}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

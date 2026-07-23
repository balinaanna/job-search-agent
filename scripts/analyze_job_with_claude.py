#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from analyze_job_with_codex import (
    SCHEMA_PATH,
    render_markdown,
    strict_output_schema,
    validate_analysis,
)
from validate_job_lead import load_json


ROOT = Path(__file__).resolve().parent.parent


def run_analysis(lead_id: str, claude: str, model: str) -> Path:
    lead_path = ROOT / "data/job-leads" / f"{lead_id}.json"
    if not lead_path.exists():
        raise FileNotFoundError(f"Job lead not found: {lead_id}")
    output_directory = ROOT / "jobs/analyzed" / lead_id
    output_directory.mkdir(parents=True, exist_ok=True)
    prompt = f"""
Analyze the job lead at data/job-leads/{lead_id}.json using the repository's
hermes-skills/job-fit-analyzer/SKILL.md workflow and the verified profile files.
Follow AGENTS.md. Do not browse, tailor application materials, or invent facts.
Return only a JSON object conforming exactly to the provided output schema.
Every evidence ID must exist in profile/evidence.yaml. The full evidence-based
score must supersede the preliminary discovery score.
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
        raise RuntimeError(response.get("result", "Claude Code analysis failed."))
    analysis = json.loads(response["result"])
    validate_analysis(analysis)
    final_json = output_directory / "analysis.json"
    final_json.write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    (output_directory / "analysis.md").write_text(
        render_markdown(analysis), encoding="utf-8"
    )
    return final_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze one job with Claude Code.")
    parser.add_argument("lead_id")
    parser.add_argument(
        "--claude", default=os.environ.get("CLAUDE_EXECUTABLE", "claude")
    )
    parser.add_argument(
        "--model", default=os.environ.get("CLAUDE_ANALYSIS_MODEL", "sonnet")
    )
    args = parser.parse_args()
    path = run_analysis(args.lead_id, args.claude, args.model)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

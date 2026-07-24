#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from validate_job_lead import load_json
from write_resume_with_codex import (
    TRACE_SCHEMA,
    find_workspace,
    normalize_section_headings,
    normalize_trace,
    output_schema,
)


ROOT = Path(__file__).resolve().parent.parent


def write_resume(lead_id: str, claude: str, model: str) -> Path:
    workspace = find_workspace(lead_id)
    manifest_path = workspace / "application_manifest.json"
    plan_path = workspace / "resume_plan.json"
    if not plan_path.exists():
        raise FileNotFoundError("Validated resume plan is required.")
    manifest = load_json(manifest_path)
    plan = load_json(plan_path)
    prompt = f"""
Write the tailored resume using the complete hermes-skills/resume-writer/SKILL.md
workflow and only {plan_path.relative_to(ROOT)} plus verified profile records.
Do not replan, browse, finalize, render, or submit. Return an object with
resume_markdown and trace. The trace must conform to the supplied schema.
Use resume_path {workspace / 'resume.md'}, source_plan_path {plan_path}, and
application_id {manifest['application_id']}. Keep Markdown ATS-friendly.
""".strip()
    schema = json.dumps(output_schema())
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
        raise RuntimeError(response.get("result", "Claude Code resume drafting failed."))
    payload = json.loads(response["result"])
    resume = normalize_section_headings(payload["resume_markdown"].strip()) + "\n"
    trace = payload["trace"]
    normalize_trace(trace, resume, plan)
    resume_path = workspace / "resume.md"
    resume_path.write_text(resume, encoding="utf-8")
    (workspace / "resume_trace.json").write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
    manifest["status"] = "drafting"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    validation = subprocess.run(
        [os.sys.executable, "scripts/validate_resume_draft.py", str(workspace),
         "--schema", str(TRACE_SCHEMA)], cwd=ROOT, capture_output=True, text=True,
    )
    if validation.returncode:
        details = (validation.stdout or validation.stderr).strip()
        raise ValueError(details or "Generated resume did not pass validation.")
    return resume_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lead_id")
    parser.add_argument("--claude", default=os.environ.get("CLAUDE_EXECUTABLE", "claude"))
    parser.add_argument("--model", default=os.environ.get("CLAUDE_RESUME_WRITER_MODEL", "sonnet"))
    args = parser.parse_args()
    try:
        print(write_resume(args.lead_id, args.claude, args.model))
        return 0
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"Resume could not be prepared: {exc}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

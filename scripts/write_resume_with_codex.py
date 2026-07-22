#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from analyze_job_with_codex import strict_output_schema
from build_strategy_with_codex import find_analysis
from validate_job_lead import load_json


ROOT = Path(__file__).resolve().parent.parent
TRACE_SCHEMA = ROOT / "hermes-skills/resume-writer/references/resume-trace-schema.json"


def find_workspace(lead_id: str) -> Path:
    analysis_path = find_analysis(lead_id)
    expected = str(analysis_path.relative_to(ROOT))
    for manifest_path in sorted((ROOT / "applications").glob("*/application_manifest.json")):
        manifest = load_json(manifest_path)
        if manifest.get("source", {}).get("analysis_path") == expected:
            return manifest_path.parent
    raise FileNotFoundError("Application workspace with a validated resume plan was not found.")


def output_schema() -> dict:
    trace = load_json(TRACE_SCHEMA)
    schema = {
        "type": "object",
        "properties": {
            "resume_markdown": {"type": "string"},
            "trace": {key: value for key, value in trace.items() if key != "$schema"},
        },
        "required": ["resume_markdown", "trace"],
        "additionalProperties": False,
    }
    return strict_output_schema(schema)


def normalize_trace(trace: dict, resume: str, plan: dict) -> None:
    elements = trace.get("elements", [])
    planned = {
        bullet["bullet_id"]
        for role in plan.get("experience_plan", []) if isinstance(role, dict)
        for bullet in role.get("planned_bullets", []) if isinstance(bullet, dict) and isinstance(bullet.get("bullet_id"), str)
    }
    mapped = {
        item.get("planned_bullet_id") for item in elements
        if isinstance(item, dict) and item.get("element_type") == "experience_bullet"
    }
    summary = trace["validation_summary"]
    summary["word_count"] = len(re.findall(r"\b[\w’'-]+\b", resume))
    summary["experience_bullet_count"] = sum(
        item.get("element_type") == "experience_bullet" for item in elements if isinstance(item, dict)
    )
    summary["project_bullet_count"] = sum(
        item.get("element_type") == "project_bullet" for item in elements if isinstance(item, dict)
    )
    summary["missing_planned_bullets"] = sorted(planned - mapped)


def normalize_section_headings(resume: str) -> str:
    return re.sub(r"^##\s+CORE SKILLS\s*$", "## SKILLS", resume, flags=re.MULTILINE)


def write_resume(lead_id: str, codex: str, model: str) -> Path:
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
    with tempfile.TemporaryDirectory() as directory:
        result = Path(directory) / "resume-result.json"
        schema = Path(directory) / "resume-output-schema.json"
        schema.write_text(json.dumps(output_schema()), encoding="utf-8")
        generated = subprocess.run(
            [codex, "exec", "--ephemeral", "--sandbox", "read-only", "--model", model,
             "--cd", str(ROOT), "--output-schema", str(schema),
             "--output-last-message", str(result), prompt], cwd=ROOT, capture_output=True, text=True,
        )
        if generated.returncode:
            raise ValueError("Resume drafting failed. Retry the resume step.")
        payload = json.loads(result.read_text(encoding="utf-8"))
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
    parser.add_argument("--codex", default=os.environ.get("CODEX_EXECUTABLE", "/Applications/ChatGPT.app/Contents/Resources/codex"))
    parser.add_argument("--model", default=os.environ.get("RESUME_WRITER_MODEL", "gpt-5.6-sol"))
    args = parser.parse_args()
    try:
        print(write_resume(args.lead_id, args.codex, args.model))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Resume could not be prepared: {exc}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

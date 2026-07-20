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
from validate_job_lead import load_json
from write_resume_with_codex import find_workspace

ROOT = Path(__file__).resolve().parent.parent
TRACE_SCHEMA = ROOT / "hermes-skills/cover-letter-writer/references/cover-letter-trace-schema.json"
PLAN_SCHEMA = ROOT / "hermes-skills/cover-letter-planner/references/cover-letter-plan-schema.json"


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", text))


def output_schema() -> dict:
    trace = {key: value for key, value in load_json(TRACE_SCHEMA).items() if key != "$schema"}
    return strict_output_schema({
        "type": "object",
        "properties": {"letter_markdown": {"type": "string"}, "trace": trace},
        "required": ["letter_markdown", "trace"],
        "additionalProperties": False,
    })


def normalize_trace(trace: dict, letter: str, plan: dict, workspace: Path) -> None:
    trace["application_id"] = plan["application_id"]
    trace["recommendation"] = plan["recommendation"]
    trace["plan_path"] = str((workspace / "cover_letter_plan.json").relative_to(ROOT))
    trace["letter_path"] = str((workspace / "cover_letter.md").relative_to(ROOT))
    trace["paragraph_count"] = len(trace["paragraphs"])
    trace["total_word_count"] = word_count(letter)
    trace["target_words_min"] = plan["structure"]["target_words_min"]
    trace["target_words_max"] = plan["structure"]["target_words_max"]
    trace["manifest_status"] = "cover_letter_drafting"
    plan_map = {item["paragraph_id"]: item for item in plan["paragraphs"]}
    for paragraph in trace["paragraphs"]:
        planned = plan_map[paragraph["paragraph_id"]]
        paragraph["purpose"] = planned["purpose"]
        paragraph["evidence_ids"] = planned["evidence_ids"]
        paragraph["resume_element_ids"] = planned["resume_element_ids"]
        paragraph["word_count"] = word_count(paragraph["text"])


def write_cover_letter(lead_id: str, codex: str, model: str) -> Path:
    workspace = find_workspace(lead_id)
    manifest_path = workspace / "application_manifest.json"
    manifest = load_json(manifest_path)
    plan = load_json(workspace / "cover_letter_plan.json")
    if manifest.get("status") != "cover_letter_planning":
        raise ValueError("A validated cover letter plan is required before drafting.")
    if plan.get("recommendation") not in {"write", "optional"}:
        raise ValueError("The approved plan recommends skipping the cover letter.")
    subprocess.run(
        [os.sys.executable, "scripts/validate_cover_letter_plan.py", str(workspace), "--schema", str(PLAN_SCHEMA)],
        cwd=ROOT, check=True,
    )
    prompt = f"""
Write the cover letter using the complete hermes-skills/cover-letter-writer/SKILL.md workflow.
Follow {workspace.relative_to(ROOT) / 'cover_letter_plan.json'} exactly and use only its
approved evidence and resume elements. Follow profile/writing_style.md and AGENTS.md.
Do not browse, replan, review, revise, or generate a PDF. Return letter_markdown and a complete
trace. The letter must include a greeting, exactly {plan['structure']['paragraph_count']} body
paragraphs in plan order, a concise closing, and Anna's name. Keep the complete letter within
{plan['structure']['target_words_min']}-{plan['structure']['target_words_max']} words.
""".strip()
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "cover-letter-result.json"
        schema = Path(directory) / "schema.json"
        schema.write_text(json.dumps(output_schema()), encoding="utf-8")
        subprocess.run(
            [codex, "exec", "--ephemeral", "--sandbox", "read-only", "--model", model,
             "--cd", str(ROOT), "--output-schema", str(schema),
             "--output-last-message", str(output), prompt], cwd=ROOT, check=True,
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
    letter = payload["letter_markdown"].strip() + "\n"
    trace = payload["trace"]
    normalize_trace(trace, letter, plan, workspace)
    letter_path = workspace / "cover_letter.md"
    letter_path.write_text(letter, encoding="utf-8")
    (workspace / "cover_letter_trace.json").write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
    manifest["status"] = "cover_letter_drafting"
    artifacts = manifest.setdefault("artifacts", {})
    artifacts.update({
        "cover_letter_markdown": str(letter_path.relative_to(ROOT)),
        "cover_letter_trace_json": str((workspace / "cover_letter_trace.json").relative_to(ROOT)),
    })
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    subprocess.run(
        [os.sys.executable, "scripts/validate_cover_letter_draft.py", str(workspace), "--schema", str(TRACE_SCHEMA)],
        cwd=ROOT, check=True,
    )
    return letter_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lead_id")
    parser.add_argument("--codex", default=os.environ.get("CODEX_EXECUTABLE", "/Applications/ChatGPT.app/Contents/Resources/codex"))
    parser.add_argument("--model", default=os.environ.get("COVER_LETTER_WRITER_MODEL", "gpt-5.6-sol"))
    args = parser.parse_args()
    print(write_cover_letter(args.lead_id, args.codex, args.model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

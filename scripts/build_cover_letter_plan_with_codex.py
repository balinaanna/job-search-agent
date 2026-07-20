#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from analyze_job_with_codex import strict_output_schema
from run_resume_pdf_worker import PDF_SCHEMA, pdf_python
from validate_job_lead import load_json
from write_resume_with_codex import find_workspace

ROOT = Path(__file__).resolve().parent.parent
PLAN_SCHEMA = ROOT / "hermes-skills/cover-letter-planner/references/cover-letter-plan-schema.json"


def create_strategy_handoff(workspace: Path, manifest: dict) -> Path:
    source = ROOT / manifest["source"]["strategy_path"]
    strategy = load_json(source)
    handoff = {
        "application_id": manifest["application_id"],
        "handoff_type": "approved_candidate_strategy_reference",
        "source_strategy_path": manifest["source"]["strategy_path"],
        "source_analysis_path": manifest["source"]["analysis_path"],
        "strategy_headline": strategy["strategy_headline"],
        "cover_letter_strategy": strategy["cover_letter_strategy"],
    }
    path = workspace / "candidate_strategy.json"
    path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    return path


def render_plan(plan: dict) -> str:
    lines = [
        "# Cover letter plan", "", "## Recommendation", "",
        f"**{plan['recommendation'].title()}** - {plan['strategic_role']['rationale']}", "",
        "## Core message", "", plan["core_message"]["thesis"], "",
        "## Employer motivation", "", plan["employer_motivation"]["angle"] or "No supported employer-specific angle.", "",
        "## Paragraph plan", "",
    ]
    for paragraph in plan["paragraphs"]:
        lines.extend([f"### {paragraph['paragraph_id']}", "", f"**Purpose:** {paragraph['purpose']}", "", paragraph["planned_claim"], ""])
    lines.extend([
        "## Writing controls", "",
        f"- Target: {plan['structure']['target_words_min']}-{plan['structure']['target_words_max']} words",
        f"- Paragraphs: {plan['structure']['paragraph_count']}",
        f"- Tone: {plan['writing_controls']['tone']}", "",
        "## Writer handoff", "", plan["writer_handoff"]["completion_rule"], "",
    ])
    return "\n".join(lines)


def build_cover_letter_plan(lead_id: str, codex: str, model: str) -> Path:
    workspace = find_workspace(lead_id)
    manifest_path = workspace / "application_manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("status") != "rendered":
        raise ValueError("A visually approved resume PDF is required before cover letter planning.")
    subprocess.run(
        [pdf_python(), "scripts/validate_resume_pdf.py", str(workspace), "--schema", str(PDF_SCHEMA),
         "--visual-inspection-passed", "--no-clipping", "--no-overlaps", "--no-broken-glyphs"],
        cwd=ROOT, check=True,
    )
    strategy_path = create_strategy_handoff(workspace, manifest)
    prompt = f"""
Create the cover letter plan using the complete hermes-skills/cover-letter-planner/SKILL.md workflow.
Use {workspace.relative_to(ROOT)} and the verified profile records. The job analysis is
{manifest['source']['analysis_path']}. Do not browse or draft cover-letter prose.
Return only schema-conforming JSON. Use application_id {manifest['application_id']} and
manifest_status cover_letter_planning. Decide honestly whether the letter should be write,
optional, or skip; do not assume every application benefits from one.
""".strip()
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "cover-letter-plan.json"
        schema = Path(directory) / "schema.json"
        schema.write_text(json.dumps(strict_output_schema(load_json(PLAN_SCHEMA))), encoding="utf-8")
        subprocess.run(
            [codex, "exec", "--ephemeral", "--sandbox", "read-only", "--model", model,
             "--cd", str(ROOT), "--output-schema", str(schema),
             "--output-last-message", str(output), prompt], cwd=ROOT, check=True,
        )
        plan = json.loads(output.read_text(encoding="utf-8"))
    plan["application_id"] = manifest["application_id"]
    plan["manifest_status"] = "cover_letter_planning"
    plan_path = workspace / "cover_letter_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    (workspace / "cover_letter_plan.md").write_text(render_plan(plan), encoding="utf-8")
    manifest["status"] = "cover_letter_planning"
    artifacts = manifest.setdefault("artifacts", {})
    artifacts.update({
        "candidate_strategy": str(strategy_path.relative_to(ROOT)),
        "cover_letter_plan_json": str(plan_path.relative_to(ROOT)),
        "cover_letter_plan_markdown": str((workspace / "cover_letter_plan.md").relative_to(ROOT)),
    })
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    subprocess.run(
        [os.sys.executable, "scripts/validate_cover_letter_plan.py", str(workspace), "--schema", str(PLAN_SCHEMA)],
        cwd=ROOT, check=True,
    )
    return plan_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lead_id")
    parser.add_argument("--codex", default=os.environ.get("CODEX_EXECUTABLE", "/Applications/ChatGPT.app/Contents/Resources/codex"))
    parser.add_argument("--model", default=os.environ.get("COVER_LETTER_PLAN_MODEL", "gpt-5.6-sol"))
    args = parser.parse_args()
    print(build_cover_letter_plan(args.lead_id, args.codex, args.model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

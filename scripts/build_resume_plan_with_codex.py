#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import uuid
from datetime import date
from pathlib import Path

from build_strategy_with_codex import find_analysis
from validate_job_lead import load_json


ROOT = Path(__file__).resolve().parent.parent
PLAN_SCHEMA = ROOT / "hermes-skills/resume-planner/references/resume-plan-schema.json"
MANIFEST_SCHEMA = ROOT / "hermes-skills/resume-planner/references/application-manifest-schema.json"


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def create_manifest(analysis_path: Path, strategy_path: Path, workspace: Path) -> dict:
    analysis = load_json(analysis_path)
    application_slug = workspace.name
    return {
        "application_id": str(uuid.uuid4()),
        "application_slug": application_slug,
        "company": analysis["job"]["company"],
        "role": analysis["job"]["title"],
        "status": "planning",
        "created_date": date.today().isoformat(),
        "source": {
            "exploration_slug": analysis_path.parent.name,
            "analysis_path": str(analysis_path.relative_to(ROOT)),
            "strategy_path": str(strategy_path.relative_to(ROOT)),
        },
        "fit": {"recommendation": analysis["recommendation"], "score": analysis["score"]["total_score"]},
        "artifacts": {
            "resume_plan_json": f"{workspace.relative_to(ROOT)}/resume_plan.json",
            "resume_plan_markdown": f"{workspace.relative_to(ROOT)}/resume_plan.md",
            "resume_markdown": f"{workspace.relative_to(ROOT)}/resume.md",
            "resume_review_json": f"{workspace.relative_to(ROOT)}/resume_review.json",
            "resume_review_markdown": f"{workspace.relative_to(ROOT)}/resume_review.md",
            "final_resume_pdf": f"{workspace.relative_to(ROOT)}/final_resume.pdf",
            "cover_letter_markdown": f"{workspace.relative_to(ROOT)}/cover_letter.md",
            "application_answers_markdown": f"{workspace.relative_to(ROOT)}/application_answers.md",
            "interview_package_markdown": f"{workspace.relative_to(ROOT)}/interview_package.md",
        },
        "submission": {"submitted": False, "submitted_date": None, "source_url": None, "notes": ""},
    }


def render_plan(plan: dict) -> str:
    lines = [
        f"# Resume plan — {plan['source']['company']} {plan['source']['role']}", "",
        f"**Format:** {plan['resume_format']['length'].replace('_', ' ')}", "",
        "## Target identity", "", plan["target_identity"]["headline"], "",
        *[f"- {item}" for item in plan["target_identity"]["messages"]],
        "", "## Section plan", "",
    ]
    for section in sorted(plan["section_plan"], key=lambda item: item["order"]):
        if section["included"]:
            lines.append(f"- **{section['section'].replace('_', ' ').title()}:** {section['purpose']}")
    lines.extend(["", "## Writer handoff", "", json.dumps(plan["writer_handoff"], indent=2), ""])
    return "\n".join(lines)


def build_resume_plan(lead_id: str, codex: str, model: str) -> Path:
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
Return only schema-conforming JSON. Use application_id {manifest['application_id']},
application_slug {manifest['application_slug']}, workspace_path {workspace.relative_to(ROOT)},
and mode {'practice_only' if manifest['fit']['recommendation'] == 'do_not_apply' else 'active_application'}.
""".strip()
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "resume-plan.json"
        subprocess.run(
            [codex, "exec", "--ephemeral", "--sandbox", "read-only", "--model", model,
             "--cd", str(ROOT), "--output-last-message", str(output), prompt], cwd=ROOT, check=True,
        )
        raw = output.read_text(encoding="utf-8").strip()
        if raw.startswith("```json") and raw.endswith("```"):
            raw = raw[7:-3].strip()
        plan = json.loads(raw)
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
    parser.add_argument("--codex", default=os.environ.get("CODEX_EXECUTABLE", "/Applications/ChatGPT.app/Contents/Resources/codex"))
    parser.add_argument("--model", default=os.environ.get("RESUME_PLAN_MODEL", "gpt-5.6-sol"))
    args = parser.parse_args()
    print(build_resume_plan(args.lead_id, args.codex, args.model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

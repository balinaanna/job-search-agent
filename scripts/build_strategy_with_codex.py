#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from analyze_job_with_codex import strict_output_schema
from surface_fit_queue import join_results, load_leads, load_valid_analyses
from validate_job_lead import load_json


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "hermes-skills/candidate-strategy/references/candidate-strategy-schema.json"


def find_analysis(lead_id: str) -> Path:
    direct = ROOT / "jobs/analyzed" / lead_id / "analysis.json"
    if direct.exists():
        return direct
    results, _ = join_results(
        load_leads(ROOT / "data/job-leads"),
        load_valid_analyses(ROOT / "jobs/analyzed", ROOT / "profile/evidence.yaml"),
    )
    match = next((item for item in results if item.lead["lead_id"] == lead_id), None)
    if match is None:
        raise FileNotFoundError(f"Validated analysis not found for {lead_id}")
    return match.analysis_path


def render_markdown(strategy: dict) -> str:
    positioning = strategy["positioning"]
    lines = [
        f"# {strategy['strategy_headline']}", "", "## Original fit verdict", "",
        f"{strategy['source_analysis']['recommendation'].replace('_', ' ').title()} — {strategy['source_analysis']['total_score']}/100",
        "", "## Hiring-manager mindset", "",
        *[f"- {item}" for item in strategy["hiring_manager_mindset"]],
        "", "## Candidate positioning", "", positioning["positioning_statement"], "",
        *[f"- {item}" for item in positioning["pillars"]],
        "", "## Most important risks", "",
    ]
    for group, risks in strategy["risks"].items():
        for item in risks:
            lines.append(f"- **{group.title()} ({item['severity']}):** {item['risk']} — {item['mitigation']}")
    lines.extend(["", "## Downstream handoffs", ""])
    for name, handoff in strategy["downstream_handoffs"].items():
        lines.extend([f"### {name.replace('_', ' ').title()}", "", f"Tone: {handoff['tone']}", ""])
    return "\n".join(lines) + "\n"


def build_strategy(lead_id: str, codex: str, model: str) -> Path:
    analysis_path = find_analysis(lead_id)
    analysis = load_json(analysis_path)
    prompt = f"""
Build the candidate strategy from {analysis_path.relative_to(ROOT)} using the complete
hermes-skills/candidate-strategy/SKILL.md workflow and verified profile files.
Follow AGENTS.md. Preserve the analysis score and recommendation. Do not browse,
write application documents, or invent facts. Return only schema-conforming JSON.
Set job.exploration_slug to {analysis_path.parent.name} and source_analysis.analysis_path
to {analysis_path.relative_to(ROOT)}.
""".strip()
    with tempfile.TemporaryDirectory() as directory:
        result = Path(directory) / "strategy.json"
        strict_schema = Path(directory) / "strict-strategy-schema.json"
        strict_schema.write_text(
            json.dumps(strict_output_schema(load_json(SCHEMA_PATH))), encoding="utf-8"
        )
        generated = subprocess.run(
            [codex, "exec", "--ephemeral", "--sandbox", "read-only", "--model", model,
             "--cd", str(ROOT), "--output-schema", str(strict_schema),
             "--output-last-message", str(result), prompt],
            cwd=ROOT, capture_output=True, text=True,
        )
        if generated.returncode:
            raise ValueError("Strategy generation failed. Retry the strategy step.")
        strategy = json.loads(result.read_text(encoding="utf-8"))
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
    parser.add_argument("--codex", default=os.environ.get("CODEX_EXECUTABLE", "/Applications/ChatGPT.app/Contents/Resources/codex"))
    parser.add_argument("--model", default=os.environ.get("JOB_STRATEGY_MODEL", "gpt-5.6-sol"))
    args = parser.parse_args()
    try:
        print(build_strategy(args.lead_id, args.codex, args.model))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Strategy could not be prepared: {exc}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

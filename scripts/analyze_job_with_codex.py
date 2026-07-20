#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator

from validate_job_analysis import (
    collect_referenced_ids,
    load_evidence_ids,
    validate_recommendation,
    validate_scores,
)
from validate_job_lead import load_json


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "hermes-skills/job-fit-analyzer/references/analysis-schema.json"
EVIDENCE_PATH = ROOT / "profile/evidence.yaml"


def validate_analysis(analysis: dict) -> None:
    schema = load_json(SCHEMA_PATH)
    Draft202012Validator(schema).validate(analysis)
    errors = validate_scores(analysis) + validate_recommendation(analysis)
    unknown = sorted(collect_referenced_ids(analysis) - load_evidence_ids(EVIDENCE_PATH))
    if unknown:
        errors.append("Unknown evidence IDs: " + ", ".join(unknown))
    if errors:
        raise ValueError("; ".join(errors))


def strict_output_schema(schema: dict) -> dict:
    """Return an API-compatible strict schema without changing validation rules."""
    strict = copy.deepcopy(schema)

    def visit(node: object) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if node.get("type") == "object" and isinstance(properties, dict):
                node["required"] = list(properties)
                node["additionalProperties"] = False
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(strict)
    return strict


def render_markdown(analysis: dict) -> str:
    job = analysis["job"]
    score = analysis["score"]
    summary = analysis["summary"]
    lines = [
        f"# {job['company']} — {job['title']}",
        "",
        "## Verdict",
        "",
        f"**{analysis['recommendation'].replace('_', ' ').title()} — {score['total_score']}/100**",
        "",
        score.get("rationale", ""),
        "",
        "## Strongest reasons",
        "",
        *[f"- {reason}" for reason in summary["strongest_reasons"]],
        "",
        "## Main risk",
        "",
        summary["main_risk"],
        "",
        "## Recommended next action",
        "",
        summary["recommended_next_action"],
        "",
        "## Requirement map",
        "",
    ]
    for item in analysis["requirement_map"]:
        lines.extend(
            [
                f"### {item['requirement']}",
                "",
                f"- Importance: {item['importance']}",
                f"- Match: {item['match']}",
                f"- Risk: {item['risk']}",
                f"- Evidence: {', '.join(item['evidence_ids']) or 'None'}",
                f"- Assessment: {item['reasoning']}",
                "",
            ]
        )
    return "\n".join(lines)


def run_analysis(lead_id: str, codex: str, model: str) -> Path:
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
    with tempfile.TemporaryDirectory() as directory:
        result_path = Path(directory) / "analysis.json"
        output_schema_path = Path(directory) / "strict-analysis-schema.json"
        output_schema_path.write_text(
            json.dumps(strict_output_schema(load_json(SCHEMA_PATH))), encoding="utf-8"
        )
        subprocess.run(
            [
                codex,
                "exec",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--model",
                model,
                "--cd",
                str(ROOT),
                "--output-schema",
                str(output_schema_path),
                "--output-last-message",
                str(result_path),
                prompt,
            ],
            cwd=ROOT,
            check=True,
        )
        analysis = json.loads(result_path.read_text(encoding="utf-8"))
    validate_analysis(analysis)
    final_json = output_directory / "analysis.json"
    final_json.write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    (output_directory / "analysis.md").write_text(
        render_markdown(analysis), encoding="utf-8"
    )
    return final_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze one job with Codex.")
    parser.add_argument("lead_id")
    parser.add_argument(
        "--codex",
        default=os.environ.get(
            "CODEX_EXECUTABLE", "/Applications/ChatGPT.app/Contents/Resources/codex"
        ),
    )
    parser.add_argument(
        "--model", default=os.environ.get("JOB_ANALYSIS_MODEL", "gpt-5.6-sol")
    )
    args = parser.parse_args()
    path = run_analysis(args.lead_id, args.codex, args.model)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

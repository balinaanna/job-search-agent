#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return value


def collect_evidence_ids(value) -> set[str]:
    ids: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"id", "evidence_id"} and isinstance(child, str):
                ids.add(child)
            elif key == "evidence_ids" and isinstance(child, list):
                ids.update(item for item in child if isinstance(item, str))
            ids.update(collect_evidence_ids(child))
    elif isinstance(value, list):
        for child in value:
            ids.update(collect_evidence_ids(child))
    return ids


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path.home()
        / ".hermes/skills/cover-letter-planner/references/cover-letter-plan-schema.json",
    )
    parser.add_argument(
        "--profile-evidence",
        type=Path,
        default=Path("profile/evidence.json"),
    )
    args = parser.parse_args()

    workspace = args.workspace
    manifest_path = workspace / "application_manifest.json"
    strategy_path = workspace / "candidate_strategy.json"
    resume_plan_path = workspace / "resume_plan.json"
    trace_path = workspace / "resume_trace.json"
    pdf_release_path = workspace / "resume_pdf_release.json"
    plan_path = workspace / "cover_letter_plan.json"
    plan_md_path = workspace / "cover_letter_plan.md"

    try:
        manifest = load_json(manifest_path)
        strategy = load_json(strategy_path)
        resume_plan = load_json(resume_plan_path)
        trace = load_json(trace_path)
        pdf_release = load_json(pdf_release_path)
        plan = load_json(plan_path)
        schema = load_json(args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []

    for error in Draft202012Validator(schema).iter_errors(plan):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"schema {location}: {error.message}")

    app_id = manifest.get("application_id")
    for name, value in [
        ("strategy", strategy.get("application_id")),
        ("resume plan", resume_plan.get("application", {}).get("application_id")),
        ("resume trace", trace.get("application_id")),
        ("PDF release", pdf_release.get("application_id")),
        ("cover letter plan", plan.get("application_id")),
    ]:
        if value != app_id:
            errors.append(f"{name} application ID does not match manifest.")

    if manifest.get("status") != "cover_letter_planning":
        errors.append("Manifest status must be cover_letter_planning.")
    if pdf_release.get("manifest_status") != "rendered":
        errors.append("Resume PDF release must be rendered.")
    validation = pdf_release.get("validation", {})
    required_pdf_checks = [
        "finalization_valid",
        "source_hash_matches_finalization",
        "pdf_snapshot_matches",
        "text_fidelity_passed",
        "visual_inspection_passed",
        "no_clipping",
        "no_overlaps",
        "no_broken_glyphs",
    ]
    failed_pdf_checks = [key for key in required_pdf_checks if validation.get(key) is not True]
    if failed_pdf_checks:
        errors.append("PDF release checks failed: " + ", ".join(failed_pdf_checks))

    paragraph_ids = [p.get("paragraph_id") for p in plan.get("paragraphs", [])]
    handoff_order = plan.get("writer_handoff", {}).get("paragraph_order", [])
    if paragraph_ids != handoff_order:
        errors.append("Writer handoff paragraph order must match paragraph array order.")

    structure = plan.get("structure", {})
    if structure.get("paragraph_count") != len(paragraph_ids):
        errors.append("paragraph_count does not match number of planned paragraphs.")
    if structure.get("target_words_min", 0) > structure.get("target_words_max", 0):
        errors.append("target_words_min cannot exceed target_words_max.")

    trace_ids = collect_evidence_ids(trace)
    resume_element_ids = {
        element.get("element_id")
        for element in trace.get("elements", [])
        if isinstance(element, dict)
    }
    strategy_ids = collect_evidence_ids(strategy)

    for paragraph in plan.get("paragraphs", []):
        for element_id in paragraph.get("resume_element_ids", []):
            if element_id not in resume_element_ids:
                errors.append(
                    f"{paragraph.get('paragraph_id')} references unknown resume element: "
                    f"{element_id}"
                )
        for evidence_id in paragraph.get("evidence_ids", []):
            if evidence_id not in trace_ids and evidence_id not in strategy_ids:
                errors.append(
                    f"{paragraph.get('paragraph_id')} references unresolved evidence ID: "
                    f"{evidence_id}"
                )

    if plan.get("recommendation") == "skip" and len(plan.get("paragraphs", [])) > 1:
        errors.append("A skip recommendation should not contain a full multi-paragraph plan.")

    if not plan_md_path.exists():
        errors.append(f"Missing Markdown plan: {plan_md_path}")

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Cover letter plan validation passed.")
    print(f"Application: {manifest['company']} — {manifest['role']}")
    print(f"Recommendation: {plan['recommendation']}")
    print(
        f"Target length: {structure['target_words_min']}-"
        f"{structure['target_words_max']} words"
    )
    print(f"Paragraphs: {structure['paragraph_count']}")
    print(f"Manifest status: {manifest['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

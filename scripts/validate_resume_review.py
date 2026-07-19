#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path.home()
        / ".hermes/skills/resume-reviewer/references/resume-review-schema.json",
    )
    args = parser.parse_args()

    manifest_path = args.workspace / "application_manifest.json"
    plan_path = args.workspace / "resume_plan.json"
    trace_path = args.workspace / "resume_trace.json"
    review_path = args.workspace / "resume_review.json"
    review_md_path = args.workspace / "resume_review.md"

    try:
        manifest = load_json(manifest_path)
        plan = load_json(plan_path)
        trace = load_json(trace_path)
        review = load_json(review_path)
        schema = load_json(args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []

    for error in Draft202012Validator(schema).iter_errors(review):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"schema {location}: {error.message}")

    application_id = manifest.get("application_id")
    if plan.get("application", {}).get("application_id") != application_id:
        errors.append("Plan application ID does not match manifest.")
    if trace.get("application_id") != application_id:
        errors.append("Trace application ID does not match manifest.")
    if review.get("application_id") != application_id:
        errors.append("Review application ID does not match manifest.")

    if manifest.get("status") != "review":
        errors.append("Manifest status must be review.")

    expected_resume_path = str(args.workspace / "resume.md")
    expected_plan_path = str(plan_path)
    expected_strategy_path = plan.get("source", {}).get("strategy_path")

    if review.get("resume_path") != expected_resume_path:
        errors.append("Review resume_path is incorrect.")
    if review.get("source_plan_path") != expected_plan_path:
        errors.append("Review source_plan_path is incorrect.")
    if review.get("source_strategy_path") != expected_strategy_path:
        errors.append("Review source_strategy_path is incorrect.")

    score = review.get("review_score", {})
    component_names = [
        "first_scan_clarity",
        "strategic_alignment",
        "evidence_accomplishments",
        "relevance_keyword_coverage",
        "readability_structure",
        "credibility_defensibility",
    ]
    calculated_total = sum(score.get(name, 0) for name in component_names)
    if calculated_total != score.get("total"):
        errors.append(
            f"Score total is {score.get('total')}; components sum to {calculated_total}."
        )

    findings = [
        item
        for item in review.get("findings", [])
        if isinstance(item, dict)
    ]
    finding_ids = [item.get("finding_id") for item in findings]
    unique_ids = len(finding_ids) == len(set(finding_ids))
    if not unique_ids:
        errors.append("Finding IDs are not unique.")

    counts = {
        severity: sum(1 for item in findings if item.get("severity") == severity)
        for severity in ("critical", "high", "medium", "low")
    }
    summary = review.get("validation_summary", {})
    for severity, count in counts.items():
        key = f"{severity}_count"
        if summary.get(key) != count:
            errors.append(
                f"{key} is {summary.get(key)}; actual count is {count}."
            )

    if summary.get("all_finding_ids_unique") is not unique_ids:
        errors.append("all_finding_ids_unique is inaccurate.")

    total = score.get("total", 0)
    critical_count = counts["critical"]
    expected_verdict = (
        "rewrite_required"
        if total < 65
        else "major_revision"
        if total < 80
        else "minor_revision"
        if total < 90
        else "ready"
    )
    if critical_count > 0 and expected_verdict == "ready":
        expected_verdict = "minor_revision"

    if review.get("verdict") != expected_verdict:
        errors.append(
            f"Verdict should be {expected_verdict} for score {total} "
            f"with {critical_count} critical findings."
        )

    if summary.get("score_components_valid") is not (calculated_total == score.get("total")):
        errors.append("score_components_valid is inaccurate.")
    if summary.get("verdict_consistent") is not (review.get("verdict") == expected_verdict):
        errors.append("verdict_consistent is inaccurate.")

    planned_bullet_ids = set()
    for entry in plan.get("experience_plan", []):
        if isinstance(entry, dict):
            for bullet in entry.get("planned_bullets", []):
                if isinstance(bullet, dict) and isinstance(bullet.get("bullet_id"), str):
                    planned_bullet_ids.add(bullet["bullet_id"])

    brief = review.get("revision_brief", {})
    for key in (
        "planned_bullet_ids_to_revise",
        "planned_bullet_ids_to_remove",
        "planned_bullet_order",
    ):
        for bullet_id in brief.get(key, []):
            if bullet_id not in planned_bullet_ids:
                errors.append(f"{key} contains unknown planned bullet ID: {bullet_id}")

    critical_findings = {
        item["finding_id"]
        for item in findings
        if item.get("severity") == "critical"
    }
    critical_locations = {
        item.get("location")
        for item in findings
        if item.get("severity") == "critical"
    }
    if critical_findings and not brief.get("sections_to_revise"):
        errors.append("Critical findings exist but revision brief has no sections to revise.")
    if critical_locations and not any(
        location in " ".join(brief.get("sections_to_revise", []))
        or any(section.lower() in str(location).lower() for section in brief.get("sections_to_revise", []))
        for location in critical_locations
    ):
        errors.append("Revision brief does not clearly cover critical finding locations.")

    if not review_md_path.exists():
        errors.append(f"Missing file: {review_md_path}")

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Resume review validation passed.")
    print(f"Application: {manifest['company']} — {manifest['role']}")
    print(f"Review score: {total}/100")
    print(f"Verdict: {review['verdict']}")
    print(f"Critical findings: {counts['critical']}")
    print(f"High findings: {counts['high']}")
    print(f"Manifest status: {manifest['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return value


def word_count(path: Path) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", path.read_text(encoding="utf-8")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path.home()
        / ".hermes/skills/resume-reviser/references/resume-revision-schema.json",
    )
    args = parser.parse_args()

    manifest_path = args.workspace / "application_manifest.json"
    plan_path = args.workspace / "resume_plan.json"
    review_path = args.workspace / "resume_review.json"
    revision_path = args.workspace / "resume_revision.json"
    revision_md_path = args.workspace / "resume_revision.md"
    resume_path = args.workspace / "resume.md"
    trace_path = args.workspace / "resume_trace.json"

    try:
        manifest = load_json(manifest_path)
        plan = load_json(plan_path)
        review = load_json(review_path)
        revision = load_json(revision_path)
        schema = load_json(args.schema)
        trace = load_json(trace_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []

    for error in Draft202012Validator(schema).iter_errors(revision):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"schema {location}: {error.message}")

    app_id = manifest.get("application_id")
    if plan.get("application", {}).get("application_id") != app_id:
        errors.append("Plan application ID does not match manifest.")
    if review.get("application_id") != app_id:
        errors.append("Review application ID does not match manifest.")
    if revision.get("application_id") != app_id:
        errors.append("Revision application ID does not match manifest.")
    if trace.get("application_id") != app_id:
        errors.append("Trace application ID does not match manifest.")

    if manifest.get("status") != "drafting":
        errors.append("Manifest status must be drafting.")
    if revision.get("manifest_status") != "drafting":
        errors.append("Revision manifest_status must be drafting.")

    revision_number = revision.get("revision_number")
    backups = revision.get("backup_paths", {})
    expected_backup_names = {
        "resume": f"resume_v{revision_number}.md",
        "trace": f"resume_trace_v{revision_number}.json",
        "review_json": f"resume_review_v{revision_number}.json",
        "review_markdown": f"resume_review_v{revision_number}.md",
    }
    for key, filename in expected_backup_names.items():
        path = Path(backups.get(key, ""))
        if path.name != filename:
            errors.append(f"Backup {key} should be named {filename}.")
        if not path.exists():
            errors.append(f"Missing backup: {path}")

    outputs = revision.get("output_paths", {})
    expected_outputs = {
        "resume": str(resume_path),
        "trace": str(trace_path),
        "revision_markdown": str(revision_md_path),
    }
    for key, expected in expected_outputs.items():
        if outputs.get(key) != expected:
            errors.append(f"Output path {key} should be {expected}.")

    finding_map = {
        item.get("finding_id"): item
        for item in review.get("findings", [])
        if isinstance(item, dict)
    }
    dispositions = {
        item.get("finding_id"): item
        for item in revision.get("findings_disposition", [])
        if isinstance(item, dict)
    }

    for finding_id, finding in finding_map.items():
        if finding.get("severity") in {"critical", "high"} and finding_id not in dispositions:
            errors.append(f"Missing disposition for {finding.get('severity')} finding {finding_id}.")

    for finding_id, disposition in dispositions.items():
        if finding_id not in finding_map:
            errors.append(f"Disposition references unknown finding ID: {finding_id}")
        elif disposition.get("severity") != finding_map[finding_id].get("severity"):
            errors.append(f"Severity mismatch for finding {finding_id}.")

    planned_bullets = set()
    for entry in plan.get("experience_plan", []):
        if isinstance(entry, dict):
            for bullet in entry.get("planned_bullets", []):
                if isinstance(bullet, dict) and isinstance(bullet.get("bullet_id"), str):
                    planned_bullets.add(bullet["bullet_id"])

    authorized_removed = set(
        review.get("revision_brief", {}).get("planned_bullet_ids_to_remove", [])
    )
    removed = set(revision.get("removed_planned_bullet_ids", []))
    if not removed.issubset(authorized_removed):
        errors.append(
            "Revision removed unauthorized planned bullets: "
            + ", ".join(sorted(removed - authorized_removed))
        )

    authorized_order = set(
        review.get("revision_brief", {}).get("planned_bullet_order", [])
    )
    reordered = set(revision.get("reordered_planned_bullet_ids", []))
    if not reordered.issubset(authorized_order):
        errors.append(
            "Revision reordered unauthorized planned bullets: "
            + ", ".join(sorted(reordered - authorized_order))
        )

    for bullet_id in removed | reordered:
        if bullet_id not in planned_bullets:
            errors.append(f"Revision references unknown planned bullet ID: {bullet_id}")

    changed_ids = [item.get("element_id") for item in revision.get("changed_elements", [])]
    if len(changed_ids) != len(set(changed_ids)):
        errors.append("Changed element IDs are not unique.")

    before_path = Path(backups.get("resume", ""))
    if before_path.exists():
        before = word_count(before_path)
        if revision.get("word_counts", {}).get("before") != before:
            errors.append(f"Before word count should be {before}.")
    if resume_path.exists():
        after = word_count(resume_path)
        if revision.get("word_counts", {}).get("after") != after:
            errors.append(f"After word count should be {after}.")

    if not revision_md_path.exists():
        errors.append(f"Missing file: {revision_md_path}")
    if not resume_path.exists():
        errors.append(f"Missing file: {resume_path}")
    if not trace_path.exists():
        errors.append(f"Missing file: {trace_path}")

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    dispositions_list = revision["findings_disposition"]
    applied = sum(
        1
        for item in dispositions_list
        if item["status"] in {"applied", "partially_applied"}
    )
    conflicts = sum(
        1
        for item in dispositions_list
        if item["status"] == "conflict"
    )

    print("Resume revision validation passed.")
    print(f"Application: {manifest['company']} — {manifest['role']}")
    print(f"Revision: {revision_number}")
    print(f"Findings applied or partially applied: {applied}")
    print(f"Conflicts: {conflicts}")
    print(f"Manifest status: {manifest['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

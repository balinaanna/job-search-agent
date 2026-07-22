#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def ids_from_list(data, keys):
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return {x["id"] for x in value if isinstance(x, dict) and isinstance(x.get("id"), str)}
    return set()


def expected_sections(plan):
    labels = {
        "professional_summary": "PROFESSIONAL SUMMARY",
        "core_skills": "SKILLS",
        "professional_experience": "PROFESSIONAL EXPERIENCE",
        "selected_projects": "SELECTED PROJECTS",
        "education": "EDUCATION",
        "certifications": "CERTIFICATIONS",
        "additional_information": "ADDITIONAL INFORMATION"
    }
    items = [x for x in plan.get("section_plan", []) if isinstance(x, dict) and x.get("included") and x.get("section") != "header"]
    items.sort(key=lambda x: x.get("order", 99))
    return [labels[x["section"]] for x in items if x.get("section") in labels]


def content_without_certifications(resume: str) -> str:
    """Credential names remain truthful even when a title keyword is excluded."""
    return re.sub(r"^##\s+CERTIFICATIONS\s*$.*?(?=^##\s+|\Z)", "", resume, flags=re.MULTILINE | re.DOTALL)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--profile-dir", type=Path, default=Path("profile"))
    parser.add_argument("--schema", type=Path,
        default=Path.home()/".hermes/skills/resume-writer/references/resume-trace-schema.json")
    parser.add_argument(
        "--expected-status",
        choices=["drafting", "review", "ready"],
        default="drafting",
        help=(
            "Manifest status expected during validation. "
            "Use 'drafting' after writing or revision, 'review' during review or "
            "finalization preflight, and 'ready' after finalization."
        ),
    )
    args = parser.parse_args()

    try:
        manifest = load_json(args.workspace/"application_manifest.json")
        plan = load_json(args.workspace/"resume_plan.json")
        trace = load_json(args.workspace/"resume_trace.json")
        schema = load_json(args.schema)
        evidence = load_yaml(args.profile_dir/"evidence.yaml")
        resume = (args.workspace/"resume.md").read_text(encoding="utf-8")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors = []
    for err in Draft202012Validator(schema).iter_errors(trace):
        loc = ".".join(map(str, err.path)) or "<root>"
        errors.append(f"schema {loc}: {err.message}")

    app_id = plan.get("application", {}).get("application_id")
    if manifest.get("application_id") != app_id or trace.get("application_id") != app_id:
        errors.append("application IDs do not match")

    actual_status = manifest.get("status")

    if actual_status != args.expected_status:
        errors.append(
            "Manifest status must be "
            f"{args.expected_status!r} for this validation stage; "
            f"found {actual_status!r}."
        )

    resume_path = args.workspace/"resume.md"
    plan_path = args.workspace/"resume_plan.json"
    if trace.get("resume_path") != str(resume_path):
        errors.append("trace resume_path is incorrect")
    if trace.get("source_plan_path") != str(plan_path):
        errors.append("trace source_plan_path is incorrect")

    actual = re.findall(r"^##\s+(.+?)\s*$", resume, flags=re.MULTILINE)
    expected = expected_sections(plan)
    if actual != expected:
        errors.append(f"section order mismatch: expected {expected}, found {actual}")

    evidence_ids = ids_from_list(evidence, ("evidence","items"))
    planned = {}
    role_limits = {}
    for entry in plan.get("experience_plan", []):
        if not isinstance(entry, dict) or entry.get("treatment") == "omit":
            continue
        rid = entry.get("role_id")
        role_limits[rid] = entry.get("bullet_limit", 0)
        for bullet in entry.get("planned_bullets", []):
            if isinstance(bullet, dict) and isinstance(bullet.get("bullet_id"), str):
                planned[bullet["bullet_id"]] = bullet

    seen = []
    role_counts = {}
    for i, element in enumerate(trace.get("elements", [])):
        if not isinstance(element, dict):
            continue
        for eid in element.get("evidence_ids", []):
            if eid not in evidence_ids:
                errors.append(f"element {i} unknown evidence ID: {eid}")
        if element.get("element_type") == "experience_bullet":
            pid = element.get("planned_bullet_id")
            if pid not in planned:
                errors.append(f"element {i} unknown planned bullet ID: {pid}")
                continue
            seen.append(pid)
            allowed = set(planned[pid].get("evidence_ids", []))
            used = set(element.get("evidence_ids", []))
            if not used:
                errors.append(f"element {i} has no evidence")
            if not used.issubset(allowed):
                errors.append(f"element {i} uses evidence not allowed by {pid}")
            for rid in element.get("source_record_ids", []):
                if rid in role_limits:
                    role_counts[rid] = role_counts.get(rid, 0) + 1

    duplicates = sorted({x for x in seen if seen.count(x) > 1})
    if duplicates:
        errors.append("planned bullets mapped twice: " + ", ".join(duplicates))

    missing = sorted(set(planned)-set(seen))
    reported = sorted(trace.get("validation_summary", {}).get("missing_planned_bullets", []))
    if missing != reported:
        errors.append(f"missing_planned_bullets should be {missing}")

    for rid, count in role_counts.items():
        if count > role_limits[rid]:
            errors.append(f"{rid} exceeds bullet limit")

    keyword_content = content_without_certifications(resume)
    for item in plan.get("excluded_keywords", []):
        if isinstance(item, dict) and isinstance(item.get("term"), str):
            term = item["term"]
            if re.search(rf"\b{re.escape(term)}\b", keyword_content, flags=re.IGNORECASE):
                errors.append(f"excluded keyword appears: {term}")

    words = len(re.findall(r"\b[\w’'-]+\b", resume))
    if words != trace.get("validation_summary", {}).get("word_count"):
        errors.append(f"word count mismatch: actual {words}")

    if trace.get("validation_summary", {}).get("unmapped_bullets"):
        errors.append("trace contains unmapped bullets")

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    summary = trace["validation_summary"]
    print("Resume draft validation passed.")
    print(f"Application: {manifest['company']} — {manifest['role']}")
    print(f"Resume: {resume_path}")
    print(f"Words: {summary['word_count']}")
    print(f"Experience bullets: {summary['experience_bullet_count']}")
    print(f"Project bullets: {summary['project_bullet_count']}")
    print(f"Manifest status: {manifest['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return value


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[*_#>`]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", text))


def collect_trace_element_ids(trace: dict) -> set[str]:
    ids = set()
    for element in trace.get("elements", []):
        if isinstance(element, dict) and isinstance(element.get("element_id"), str):
            ids.add(element["element_id"])
    return ids


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path.home()
        / ".hermes/skills/cover-letter-writer/references/cover-letter-trace-schema.json",
    )
    args = parser.parse_args()

    workspace = args.workspace
    manifest_path = workspace / "application_manifest.json"
    plan_path = workspace / "cover_letter_plan.json"
    letter_path = workspace / "cover_letter.md"
    trace_path = workspace / "cover_letter_trace.json"
    resume_trace_path = workspace / "resume_trace.json"
    final_resume_path = workspace / "final_resume.md"

    try:
        manifest = load_json(manifest_path)
        plan = load_json(plan_path)
        trace = load_json(trace_path)
        resume_trace = load_json(resume_trace_path)
        schema = load_json(args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []

    for error in Draft202012Validator(schema).iter_errors(trace):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"schema {location}: {error.message}")

    if not letter_path.exists():
        errors.append(f"Missing cover letter: {letter_path}")
        letter_text = ""
    else:
        letter_text = letter_path.read_text(encoding="utf-8")

    app_id = manifest.get("application_id")
    if plan.get("application_id") != app_id:
        errors.append("Plan application ID does not match manifest.")
    if trace.get("application_id") != app_id:
        errors.append("Trace application ID does not match manifest.")

    if manifest.get("status") != "cover_letter_drafting":
        errors.append("Manifest status must be cover_letter_drafting.")

    recommendation = plan.get("recommendation")
    if recommendation not in {"write", "optional"}:
        errors.append("Plan recommendation must be write or optional.")
    if trace.get("recommendation") != recommendation:
        errors.append("Trace recommendation does not match plan.")

    plan_paragraphs = plan.get("paragraphs", [])
    trace_paragraphs = trace.get("paragraphs", [])
    plan_ids = [p.get("paragraph_id") for p in plan_paragraphs]
    trace_ids = [p.get("paragraph_id") for p in trace_paragraphs]

    if trace_ids != plan_ids:
        errors.append("Paragraph order does not match plan.")
    if len(trace_paragraphs) != plan.get("structure", {}).get("paragraph_count"):
        errors.append("Paragraph count does not match plan.")

    target_min = plan.get("structure", {}).get("target_words_min")
    target_max = plan.get("structure", {}).get("target_words_max")
    actual_total = word_count(letter_text)

    if trace.get("total_word_count") != actual_total:
        errors.append(
            f"Trace total_word_count is {trace.get('total_word_count')}, "
            f"but letter contains {actual_total} words."
        )
    if not (target_min <= actual_total <= target_max):
        errors.append(
            f"Letter word count {actual_total} is outside target range "
            f"{target_min}-{target_max}."
        )

    if trace.get("paragraph_count") != len(trace_paragraphs):
        errors.append("Trace paragraph_count does not match trace paragraphs.")
    if trace.get("target_words_min") != target_min:
        errors.append("Trace target_words_min does not match plan.")
    if trace.get("target_words_max") != target_max:
        errors.append("Trace target_words_max does not match plan.")

    resume_element_ids = collect_trace_element_ids(resume_trace)

    for planned, written in zip(plan_paragraphs, trace_paragraphs):
        if written.get("purpose") != planned.get("purpose"):
            errors.append(
                f"{written.get('paragraph_id')} purpose does not match plan."
            )
        if set(written.get("evidence_ids", [])) != set(planned.get("evidence_ids", [])):
            errors.append(
                f"{written.get('paragraph_id')} evidence IDs do not match plan."
            )
        if set(written.get("resume_element_ids", [])) != set(
            planned.get("resume_element_ids", [])
        ):
            errors.append(
                f"{written.get('paragraph_id')} resume element IDs do not match plan."
            )
        for element_id in written.get("resume_element_ids", []):
            if element_id not in resume_element_ids:
                errors.append(
                    f"{written.get('paragraph_id')} references unknown resume element "
                    f"{element_id}."
                )

        wc = word_count(written.get("text", ""))
        if written.get("word_count") != wc:
            errors.append(
                f"{written.get('paragraph_id')} word count should be {wc}."
            )

    forbidden_phrases = set(plan.get("writing_controls", {}).get("forbidden_phrases", []))
    normalized_letter = normalize(letter_text)
    for phrase in forbidden_phrases:
        if normalize(phrase) in normalized_letter:
            errors.append(f"Forbidden phrase found: {phrase}")

    final_resume_text = final_resume_path.read_text(encoding="utf-8")
    resume_lines = [
        normalize(line)
        for line in final_resume_text.splitlines()
        if len(normalize(line).split()) >= 8
    ]
    for line in resume_lines:
        if line and line in normalized_letter:
            errors.append(
                "Potential verbatim resume duplication found: "
                f"{line[:100]}"
            )
            break

    validation = trace.get("validation", {})
    false_checks = [key for key, value in validation.items() if value is not True]
    if false_checks:
        errors.append("Trace validation checks are false: " + ", ".join(false_checks))

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Cover letter draft validation passed.")
    print(f"Application: {manifest['company']} — {manifest['role']}")
    print(f"Paragraphs: {len(trace_paragraphs)}")
    print(f"Word count: {actual_total}")
    print(f"Target range: {target_min}-{target_max}")
    print(f"Manifest status: {manifest['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

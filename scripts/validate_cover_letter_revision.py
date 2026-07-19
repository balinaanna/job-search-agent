#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", text))


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[*_#>`]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path.home()
        / ".hermes/skills/cover-letter-reviser/references/"
        / "cover-letter-revision-schema.json",
    )
    args = parser.parse_args()

    workspace = args.workspace

    try:
        manifest = load_json(workspace / "application_manifest.json")
        plan = load_json(workspace / "cover_letter_plan.json")
        trace = load_json(workspace / "cover_letter_trace.json")
        review = load_json(workspace / "cover_letter_review.json")
        revision = load_json(workspace / "cover_letter_revision.json")
        schema = load_json(args.schema)
        current_letter = (workspace / "cover_letter.md").read_text(encoding="utf-8")
        final_resume = (workspace / "final_resume.md").read_text(encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []

    for error in Draft202012Validator(schema).iter_errors(revision):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"schema {location}: {error.message}")

    app_id = manifest.get("application_id")
    for name, value in [
        ("plan", plan.get("application_id")),
        ("trace", trace.get("application_id")),
        ("review", review.get("application_id")),
        ("revision", revision.get("application_id")),
    ]:
        if value != app_id:
            errors.append(f"{name} application ID does not match manifest.")

    if manifest.get("status") != "cover_letter_revision":
        errors.append("Manifest status must be cover_letter_revision.")

    expected_verdicts = {"minor_revision", "major_revision", "rewrite_required"}
    review_verdict = review.get("verdict")
    if review_verdict not in expected_verdicts:
        errors.append("Source review verdict does not permit revision.")

    source_review = revision.get("source_review", {})
    if source_review.get("score") != review.get("score"):
        errors.append("Revision source score does not match review.")
    if source_review.get("verdict") != review_verdict:
        errors.append("Revision source verdict does not match review.")

    version = revision.get("version")
    expected_snapshot_names = {
        "cover_letter": f"versions/cover_letter_v{version}.md",
        "cover_letter_trace": f"versions/cover_letter_trace_v{version}.json",
        "cover_letter_review_json": f"versions/cover_letter_review_v{version}.json",
        "cover_letter_review_markdown": f"versions/cover_letter_review_v{version}.md",
    }

    snapshot_types = set()
    for snapshot in revision.get("snapshots", []):
        artifact_type = snapshot.get("artifact_type")
        snapshot_types.add(artifact_type)
        relative = snapshot.get("path")
        if relative != expected_snapshot_names.get(artifact_type):
            errors.append(
                f"Unexpected snapshot path for {artifact_type}: {relative}"
            )
            continue
        path = workspace / relative
        if not path.exists():
            errors.append(f"Missing snapshot: {path}")
            continue
        actual_hash = sha256_file(path)
        if actual_hash != snapshot.get("sha256"):
            errors.append(f"Snapshot hash mismatch: {relative}")

    if snapshot_types != set(expected_snapshot_names):
        errors.append("Snapshot artifact set is incomplete or duplicated.")

    brief = review.get("revision_brief", {})
    authorized_ids = brief.get("authorized_paragraph_ids", [])
    priority_ids = brief.get("priority_order", [])

    if revision.get("authorized_paragraph_ids") != authorized_ids:
        errors.append("Authorized paragraph IDs do not match review brief.")

    findings_by_id = {
        finding.get("finding_id"): finding
        for finding in review.get("findings", [])
    }
    processed = revision.get("processed_findings", [])
    processed_ids = [item.get("finding_id") for item in processed]

    if processed_ids != priority_ids:
        errors.append(
            "Processed findings must exactly match review priority order."
        )

    for item in processed:
        finding = findings_by_id.get(item.get("finding_id"))
        if not finding:
            errors.append(
                f"Unknown processed finding: {item.get('finding_id')}"
            )
            continue
        if item.get("paragraph_id") != finding.get("paragraph_id"):
            errors.append(
                f"{item.get('finding_id')} paragraph does not match review."
            )
        if item.get("revision_instruction") != finding.get(
            "revision_instruction"
        ):
            errors.append(
                f"{item.get('finding_id')} instruction does not match review."
            )

    plan_paragraph_ids = [
        paragraph.get("paragraph_id")
        for paragraph in plan.get("paragraphs", [])
    ]
    trace_paragraphs = {
        paragraph.get("paragraph_id"): paragraph
        for paragraph in trace.get("paragraphs", [])
    }

    changed_ids = [
        change.get("paragraph_id")
        for change in revision.get("paragraph_changes", [])
    ]
    if len(changed_ids) != len(set(changed_ids)):
        errors.append("Duplicate paragraph changes found.")
    if not set(changed_ids).issubset(set(authorized_ids)):
        errors.append("An unauthorized paragraph was changed.")

    unchanged_ids = revision.get("unchanged_paragraph_ids", [])
    if set(changed_ids).intersection(unchanged_ids):
        errors.append("A paragraph cannot be both changed and unchanged.")
    if set(changed_ids).union(unchanged_ids) != set(plan_paragraph_ids):
        errors.append(
            "Changed and unchanged paragraph IDs must cover the full plan."
        )

    before_trace_path = workspace / f"versions/cover_letter_trace_v{version}.json"
    before_letter_path = workspace / f"versions/cover_letter_v{version}.md"
    try:
        before_trace = load_json(before_trace_path)
        before_letter = before_letter_path.read_text(encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"Cannot read source snapshots: {exc}")
        before_trace = {}
        before_letter = ""

    before_paragraphs = {
        paragraph.get("paragraph_id"): paragraph
        for paragraph in before_trace.get("paragraphs", [])
    }

    for change in revision.get("paragraph_changes", []):
        paragraph_id = change.get("paragraph_id")
        before = before_paragraphs.get(paragraph_id, {})
        after = trace_paragraphs.get(paragraph_id, {})

        if change.get("before_text") != before.get("text"):
            errors.append(f"{paragraph_id} before_text does not match snapshot.")
        if change.get("after_text") != after.get("text"):
            errors.append(f"{paragraph_id} after_text does not match trace.")
        if change.get("before_text") == change.get("after_text"):
            errors.append(f"{paragraph_id} is recorded as changed but is identical.")

        if change.get("evidence_ids_before") != before.get("evidence_ids", []):
            errors.append(f"{paragraph_id} evidence_ids_before mismatch.")
        if change.get("evidence_ids_after") != after.get("evidence_ids", []):
            errors.append(f"{paragraph_id} evidence_ids_after mismatch.")
        if set(change.get("evidence_ids_before", [])) != set(
            change.get("evidence_ids_after", [])
        ):
            errors.append(f"{paragraph_id} evidence IDs changed.")

        if change.get("resume_element_ids_before") != before.get(
            "resume_element_ids", []
        ):
            errors.append(f"{paragraph_id} resume_element_ids_before mismatch.")
        if change.get("resume_element_ids_after") != after.get(
            "resume_element_ids", []
        ):
            errors.append(f"{paragraph_id} resume_element_ids_after mismatch.")
        if set(change.get("resume_element_ids_before", [])) != set(
            change.get("resume_element_ids_after", [])
        ):
            errors.append(f"{paragraph_id} resume element IDs changed.")

        expected_before_wc = word_count(change.get("before_text", ""))
        expected_after_wc = word_count(change.get("after_text", ""))
        if change.get("word_count_before") != expected_before_wc:
            errors.append(f"{paragraph_id} before word count mismatch.")
        if change.get("word_count_after") != expected_after_wc:
            errors.append(f"{paragraph_id} after word count mismatch.")

        finding_ids = change.get("finding_ids", [])
        if not set(finding_ids).issubset(set(priority_ids)):
            errors.append(f"{paragraph_id} uses an unapproved finding.")
        for finding_id in finding_ids:
            finding = findings_by_id.get(finding_id)
            if finding and finding.get("paragraph_id") != paragraph_id:
                errors.append(
                    f"{finding_id} cannot authorize changes to {paragraph_id}."
                )

    for paragraph_id in unchanged_ids:
        before = before_paragraphs.get(paragraph_id, {})
        after = trace_paragraphs.get(paragraph_id, {})
        if before.get("text") != after.get("text"):
            errors.append(f"Unchanged paragraph {paragraph_id} was modified.")
        if before.get("evidence_ids") != after.get("evidence_ids"):
            errors.append(f"Unchanged paragraph {paragraph_id} evidence changed.")
        if before.get("resume_element_ids") != after.get("resume_element_ids"):
            errors.append(
                f"Unchanged paragraph {paragraph_id} resume references changed."
            )

    expected_order = plan_paragraph_ids
    actual_order = [
        paragraph.get("paragraph_id")
        for paragraph in trace.get("paragraphs", [])
    ]
    if actual_order != expected_order:
        errors.append("Revised trace paragraph order does not match plan.")

    if len(actual_order) != plan.get("structure", {}).get("paragraph_count"):
        errors.append("Revised paragraph count does not match plan.")

    actual_after_words = word_count(current_letter)
    actual_before_words = word_count(before_letter)
    counts = revision.get("word_counts", {})
    if counts.get("before") != actual_before_words:
        errors.append("Revision before word count mismatch.")
    if counts.get("after") != actual_after_words:
        errors.append("Revision after word count mismatch.")

    target_min = plan.get("structure", {}).get("target_words_min")
    target_max = plan.get("structure", {}).get("target_words_max")
    if counts.get("target_min") != target_min:
        errors.append("Revision target_min does not match plan.")
    if counts.get("target_max") != target_max:
        errors.append("Revision target_max does not match plan.")
    if not (target_min <= actual_after_words <= target_max):
        errors.append(
            f"Revised letter word count {actual_after_words} is outside "
            f"{target_min}-{target_max}."
        )

    trace_total = trace.get("total_word_count")
    if trace_total != actual_after_words:
        errors.append(
            f"Trace total word count {trace_total} does not match letter "
            f"{actual_after_words}."
        )

    normalized_letter = normalize(current_letter)
    forbidden_phrases = plan.get("writing_controls", {}).get(
        "forbidden_phrases", []
    )
    for phrase in forbidden_phrases:
        if normalize(phrase) in normalized_letter:
            errors.append(f"Forbidden phrase found: {phrase}")

    resume_lines = [
        normalize(line)
        for line in final_resume.splitlines()
        if len(normalize(line).split()) >= 8
    ]
    for line in resume_lines:
        if line and line in normalized_letter:
            errors.append(
                "Potential verbatim resume duplication found: "
                f"{line[:100]}"
            )
            break

    preservation = revision.get("preservation_checks", {})
    failed_preservation = [
        key for key, value in preservation.items() if value is not True
    ]
    if failed_preservation:
        errors.append(
            "Preservation checks failed: " + ", ".join(failed_preservation)
        )

    validation = revision.get("validation", {})
    failed_validation = [
        key for key, value in validation.items() if value is not True
    ]
    if failed_validation:
        errors.append(
            "Revision validation flags failed: "
            + ", ".join(failed_validation)
        )

    revision_md = workspace / "cover_letter_revision.md"
    if not revision_md.exists():
        errors.append(f"Missing revision Markdown: {revision_md}")

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    status_counts = {
        "resolved": 0,
        "partially_resolved": 0,
        "not_resolved": 0,
    }
    for item in processed:
        status_counts[item["status"]] += 1

    print("Cover letter revision validation passed.")
    print(f"Application: {manifest['company']} — {manifest['role']}")
    print(
        f"Source review: {review['score']}/100 — {review['verdict']}"
    )
    print(f"Version snapshot: v{version}")
    print(
        "Findings: "
        f"{status_counts['resolved']} resolved, "
        f"{status_counts['partially_resolved']} partially resolved, "
        f"{status_counts['not_resolved']} not resolved"
    )
    print(f"Paragraphs changed: {len(changed_ids)}")
    print(f"Word count: {actual_before_words} → {actual_after_words}")
    print(f"Manifest status: {manifest['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

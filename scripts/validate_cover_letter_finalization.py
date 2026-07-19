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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path.home()
        / ".hermes/skills/cover-letter-finalizer/references/"
        / "cover-letter-finalization-schema.json",
    )
    args = parser.parse_args()
    workspace = args.workspace

    paths = {
        "manifest": workspace / "application_manifest.json",
        "plan": workspace / "cover_letter_plan.json",
        "source": workspace / "cover_letter.md",
        "final": workspace / "final_cover_letter.md",
        "trace": workspace / "cover_letter_trace.json",
        "review": workspace / "cover_letter_review.json",
        "review_md": workspace / "cover_letter_review.md",
        "strategy": workspace / "candidate_strategy.json",
        "resume": workspace / "final_resume.md",
        "resume_trace": workspace / "resume_trace.json",
        "finalization": workspace / "cover_letter_finalization.json",
        "finalization_md": workspace / "cover_letter_finalization.md",
    }

    try:
        manifest = load_json(paths["manifest"])
        plan = load_json(paths["plan"])
        trace = load_json(paths["trace"])
        review = load_json(paths["review"])
        finalization = load_json(paths["finalization"])
        schema = load_json(args.schema)
        source_bytes = paths["source"].read_bytes()
        final_bytes = paths["final"].read_bytes()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []

    for error in Draft202012Validator(schema).iter_errors(finalization):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"schema {location}: {error.message}")

    app_id = manifest.get("application_id")
    for name, value in [
        ("plan", plan.get("application_id")),
        ("trace", trace.get("application_id")),
        ("review", review.get("application_id")),
        ("finalization", finalization.get("application_id")),
    ]:
        if value != app_id:
            errors.append(f"{name} application ID does not match manifest.")

    if finalization.get("company") != manifest.get("company"):
        errors.append("Finalization company does not match manifest.")
    if finalization.get("role") != manifest.get("role"):
        errors.append("Finalization role does not match manifest.")

    if manifest.get("status") != "cover_letter_ready":
        errors.append("Manifest status must be cover_letter_ready.")

    if review.get("verdict") != "ready":
        errors.append("Review verdict must be ready.")
    if review.get("score", 0) < 90:
        errors.append("Review score must be at least 90.")

    source_review = finalization.get("source_review", {})
    if source_review.get("score") != review.get("score"):
        errors.append("Finalization score does not match review.")
    if source_review.get("verdict") != review.get("verdict"):
        errors.append("Finalization verdict does not match review.")

    findings = review.get("findings", [])
    blocking = [
        finding for finding in findings
        if finding.get("severity") in {"critical", "high"}
    ]
    if blocking:
        errors.append("Ready review contains blocking findings.")

    authorized = review.get("revision_brief", {}).get(
        "authorized_paragraph_ids", []
    )
    if authorized:
        errors.append("Ready review must authorize no paragraph revisions.")

    if source_bytes != final_bytes:
        errors.append(
            "final_cover_letter.md is not byte-for-byte identical to "
            "cover_letter.md."
        )

    artifact_map = {
        "source_cover_letter": paths["source"],
        "final_cover_letter": paths["final"],
        "cover_letter_trace": paths["trace"],
        "cover_letter_plan": paths["plan"],
        "cover_letter_review": paths["review"],
        "candidate_strategy": paths["strategy"],
        "final_resume": paths["resume"],
        "resume_trace": paths["resume_trace"],
    }
    hash_key_map = {
        "source_cover_letter": "source_cover_letter_sha256",
        "final_cover_letter": "final_cover_letter_sha256",
        "cover_letter_trace": "cover_letter_trace_sha256",
        "cover_letter_plan": "cover_letter_plan_sha256",
        "cover_letter_review": "cover_letter_review_sha256",
        "candidate_strategy": "candidate_strategy_sha256",
        "final_resume": "final_resume_sha256",
        "resume_trace": "resume_trace_sha256",
    }

    artifacts = finalization.get("artifacts", {})
    hashes = finalization.get("release_hashes", {})
    for key, path in artifact_map.items():
        expected_relative = path.relative_to(workspace).as_posix()
        if artifacts.get(key) != expected_relative:
            errors.append(
                f"Artifact path mismatch for {key}: "
                f"expected {expected_relative}, got {artifacts.get(key)}."
            )
        if not path.exists():
            errors.append(f"Missing release artifact: {path}")
            continue
        actual_hash = sha256_file(path)
        if hashes.get(hash_key_map[key]) != actual_hash:
            errors.append(f"Hash mismatch for {key}.")

    if hashes.get("source_cover_letter_sha256") != hashes.get(
        "final_cover_letter_sha256"
    ):
        errors.append("Source and final cover letter hashes must match.")

    plan_structure = plan.get("structure", {})
    target_min = plan_structure.get("target_words_min")
    target_max = plan_structure.get("target_words_max")
    paragraph_count = plan_structure.get("paragraph_count")
    final_text = final_bytes.decode("utf-8")
    actual_words = word_count(final_text)

    if finalization.get("paragraph_count") != paragraph_count:
        errors.append("Finalization paragraph count does not match plan.")
    if finalization.get("total_word_count") != actual_words:
        errors.append("Finalization word count does not match final letter.")
    if finalization.get("target_words_min") != target_min:
        errors.append("Finalization target minimum does not match plan.")
    if finalization.get("target_words_max") != target_max:
        errors.append("Finalization target maximum does not match plan.")
    if not (target_min <= actual_words <= target_max):
        errors.append(
            f"Final letter word count {actual_words} is outside "
            f"{target_min}-{target_max}."
        )

    trace_paragraphs = trace.get("paragraphs", [])
    if len(trace_paragraphs) != paragraph_count:
        errors.append("Trace paragraph count does not match plan.")
    if trace.get("total_word_count") != actual_words:
        errors.append("Trace word count does not match final letter.")

    trace_evidence_ids = sorted({
        evidence_id
        for paragraph in trace_paragraphs
        for evidence_id in paragraph.get("evidence_ids", [])
    })
    trace_resume_ids = sorted({
        element_id
        for paragraph in trace_paragraphs
        for element_id in paragraph.get("resume_element_ids", [])
    })

    coverage = finalization.get("evidence_coverage", {})
    if sorted(coverage.get("covered_evidence_ids", [])) != trace_evidence_ids:
        errors.append("Finalization evidence IDs do not match trace.")
    if sorted(
        coverage.get("covered_resume_element_ids", [])
    ) != trace_resume_ids:
        errors.append("Finalization resume element IDs do not match trace.")
    if coverage.get("unsupported_claims"):
        errors.append("Finalization reports unsupported claims.")

    checks = finalization.get("release_checks", {})
    failed_checks = [key for key, value in checks.items() if value is not True]
    if failed_checks:
        errors.append("Release checks failed: " + ", ".join(failed_checks))

    for required_path in [
        paths["review_md"],
        paths["finalization_md"],
    ]:
        if not required_path.exists():
            errors.append(f"Missing required Markdown artifact: {required_path}")

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Cover letter finalization validation passed.")
    print(f"Application: {manifest['company']} — {manifest['role']}")
    print(f"Review: {review['score']}/100 — {review['verdict']}")
    print(f"Paragraphs: {paragraph_count}")
    print(f"Word count: {actual_words}")
    print(
        "Release SHA256: "
        f"{hashes['final_cover_letter_sha256']}"
    )
    print("Content identity: verified")
    print(f"Manifest status: {manifest['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path.home()
        / ".hermes/skills/resume-finalizer/references/resume-finalization-schema.json",
    )
    args = parser.parse_args()

    manifest_path = args.workspace / "application_manifest.json"
    plan_path = args.workspace / "resume_plan.json"
    resume_path = args.workspace / "resume.md"
    trace_path = args.workspace / "resume_trace.json"
    review_path = args.workspace / "resume_review.json"
    finalization_path = args.workspace / "resume_finalization.json"
    finalization_md_path = args.workspace / "resume_finalization.md"
    final_resume_path = args.workspace / "final_resume.md"

    try:
        manifest = load_json(manifest_path)
        plan = load_json(plan_path)
        trace = load_json(trace_path)
        review = load_json(review_path)
        finalization = load_json(finalization_path)
        schema = load_json(args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []

    for error in Draft202012Validator(schema).iter_errors(finalization):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"schema {location}: {error.message}")

    app_id = manifest.get("application_id")
    if plan.get("application", {}).get("application_id") != app_id:
        errors.append("Plan application ID does not match manifest.")
    if trace.get("application_id") != app_id:
        errors.append("Trace application ID does not match manifest.")
    if review.get("application_id") != app_id:
        errors.append("Review application ID does not match manifest.")
    if finalization.get("application_id") != app_id:
        errors.append("Finalization application ID does not match manifest.")

    if manifest.get("status") != "ready":
        errors.append("Manifest status must be ready.")
    if finalization.get("manifest_status") != "ready":
        errors.append("Finalization manifest_status must be ready.")

    score = review.get("review_score", {}).get("total")
    verdict = review.get("verdict")
    summary = review.get("validation_summary", {})
    if score is None or score < 90:
        errors.append("Review score must be at least 90.")
    if verdict != "ready":
        errors.append("Review verdict must be ready.")
    if summary.get("critical_count") != 0:
        errors.append("Critical finding count must be zero.")
    if summary.get("high_count") != 0:
        errors.append("High finding count must be zero.")

    version = finalization.get("final_version")
    outputs = finalization.get("output_paths", {})
    expected = {
        "final_resume": str(final_resume_path),
        "snapshot_resume": str(args.workspace / f"versions/final_resume_v{version}.md"),
        "snapshot_trace": str(args.workspace / f"versions/final_resume_trace_v{version}.json"),
        "snapshot_review": str(args.workspace / f"versions/final_resume_review_v{version}.json"),
        "finalization_markdown": str(finalization_md_path),
    }
    for key, value in expected.items():
        if outputs.get(key) != value:
            errors.append(f"Output path {key} should be {value}.")
        if not Path(value).exists():
            errors.append(f"Missing output file: {value}")

    source_paths = finalization.get("source_paths", {})
    expected_sources = {
        "resume": str(resume_path),
        "trace": str(trace_path),
        "review": str(review_path),
        "plan": str(plan_path),
    }
    for key, value in expected_sources.items():
        if source_paths.get(key) != value:
            errors.append(f"Source path {key} should be {value}.")

    if all(Path(path).exists() for path in [
        resume_path,
        final_resume_path,
        Path(expected["snapshot_resume"]),
        trace_path,
        Path(expected["snapshot_trace"]),
        review_path,
        Path(expected["snapshot_review"]),
        plan_path,
    ]):
        actual_hashes = {
            "source_resume_sha256": sha256(resume_path),
            "final_resume_sha256": sha256(final_resume_path),
            "snapshot_resume_sha256": sha256(Path(expected["snapshot_resume"])),
            "source_trace_sha256": sha256(trace_path),
            "snapshot_trace_sha256": sha256(Path(expected["snapshot_trace"])),
            "source_review_sha256": sha256(review_path),
            "snapshot_review_sha256": sha256(Path(expected["snapshot_review"])),
            "plan_sha256": sha256(plan_path),
        }
        for key, value in actual_hashes.items():
            if finalization.get("hashes", {}).get(key) != value:
                errors.append(f"Hash mismatch for {key}.")

        if len({
            actual_hashes["source_resume_sha256"],
            actual_hashes["final_resume_sha256"],
            actual_hashes["snapshot_resume_sha256"],
        }) != 1:
            errors.append("Final resume is not byte-identical to source resume.")

        if actual_hashes["source_trace_sha256"] != actual_hashes["snapshot_trace_sha256"]:
            errors.append("Snapshot trace differs from source trace.")
        if actual_hashes["source_review_sha256"] != actual_hashes["snapshot_review_sha256"]:
            errors.append("Snapshot review differs from source review.")

    gates = finalization.get("release_gates", {})
    false_gates = [key for key, value in gates.items() if value is not True]
    if false_gates:
        errors.append("Release gates are false: " + ", ".join(false_gates))

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Resume finalization validation passed.")
    print(f"Application: {manifest['company']} — {manifest['role']}")
    print(f"Final version: {version}")
    print(f"Review score: {score}/100")
    print(f"Final resume: {final_resume_path}")
    print(f"Manifest status: {manifest['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

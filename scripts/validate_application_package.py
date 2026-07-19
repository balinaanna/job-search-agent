#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from pypdf import PdfReader


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


def pages(path: Path) -> int:
    return len(PdfReader(str(path)).pages)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path.home()
        / ".hermes/skills/application-package-assembler/references/"
        / "application-package-schema.json",
    )
    args = parser.parse_args()
    workspace = args.workspace
    submission = workspace / "submission"

    paths = {
        "manifest": workspace / "application_manifest.json",
        "source_resume": workspace / "final_resume.pdf",
        "source_cover": workspace / "final_cover_letter.pdf",
        "resume_release": workspace / "resume_pdf_release.json",
        "cover_release": workspace / "cover_letter_pdf_release.json",
        "packaged_resume": submission / "resume.pdf",
        "packaged_cover": submission / "cover_letter.pdf",
        "package": submission / "application_package.json",
        "package_md": submission / "application_package.md",
        "checklist": submission / "submission_checklist.md",
    }

    try:
        manifest = load_json(paths["manifest"])
        resume_release = load_json(paths["resume_release"])
        cover_release = load_json(paths["cover_release"])
        package = load_json(paths["package"])
        schema = load_json(args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []

    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )
    for error in validator.iter_errors(package):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"schema {location}: {error.message}")

    if manifest.get("status") != "application_packaged":
        errors.append("Manifest status must be application_packaged.")
    if package.get("manifest_status") != "application_packaged":
        errors.append("Package manifest status is incorrect.")

    app_id = manifest.get("application_id")
    for name, artifact in [
        ("package", package),
        ("resume release", resume_release),
        ("cover letter release", cover_release),
    ]:
        if artifact.get("application_id") != app_id:
            errors.append(f"{name} application ID mismatch.")
        if artifact.get("company") != manifest.get("company"):
            errors.append(f"{name} company mismatch.")
        if artifact.get("role") != manifest.get("role"):
            errors.append(f"{name} role mismatch.")

    for path in paths.values():
        if not path.exists():
            errors.append(f"Missing required artifact: {path}")

    hashes = package.get("hashes", {})
    hash_targets = {
        "source_resume_sha256": paths["source_resume"],
        "packaged_resume_sha256": paths["packaged_resume"],
        "source_cover_letter_sha256": paths["source_cover"],
        "packaged_cover_letter_sha256": paths["packaged_cover"],
    }
    for key, path in hash_targets.items():
        if path.exists() and hashes.get(key) != sha256_file(path):
            errors.append(f"Hash mismatch for {key}.")

    if paths["source_resume"].exists() and paths["packaged_resume"].exists():
        if paths["source_resume"].read_bytes() != paths["packaged_resume"].read_bytes():
            errors.append("Packaged resume is not identical to source.")
    if paths["source_cover"].exists() and paths["packaged_cover"].exists():
        if paths["source_cover"].read_bytes() != paths["packaged_cover"].read_bytes():
            errors.append("Packaged cover letter is not identical to source.")

    recorded_resume_hash = (
        resume_release.get("hashes", {}).get("final_resume_pdf_sha256")
        or resume_release.get("release_hashes", {}).get(
            "final_resume_pdf_sha256"
        )
    )
    if paths["source_resume"].exists():
        if recorded_resume_hash != sha256_file(paths["source_resume"]):
            errors.append("Resume source hash does not match release metadata.")

    recorded_cover_hash = cover_release.get("hashes", {}).get(
        "final_cover_letter_pdf_sha256"
    )
    if paths["source_cover"].exists():
        if recorded_cover_hash != sha256_file(paths["source_cover"]):
            errors.append(
                "Cover letter source hash does not match release metadata."
            )

    page_counts = package.get("page_counts", {})
    try:
        if pages(paths["packaged_resume"]) != page_counts.get("resume"):
            errors.append("Resume page count mismatch.")
        if pages(paths["packaged_cover"]) != page_counts.get("cover_letter"):
            errors.append("Cover letter page count mismatch.")
    except Exception as exc:
        errors.append(f"Packaged PDF readability failed: {exc}")

    release_refs = package.get("release_references", {})
    if release_refs.get("resume_release_sha256") != sha256_file(
        paths["resume_release"]
    ):
        errors.append("Resume release hash mismatch.")
    if release_refs.get("cover_letter_release_sha256") != sha256_file(
        paths["cover_release"]
    ):
        errors.append("Cover letter release hash mismatch.")

    identity = package.get("identity_checks", {})
    failed_identity = [key for key, value in identity.items() if value is not True]
    if failed_identity:
        errors.append("Identity checks failed: " + ", ".join(failed_identity))

    readiness = package.get("readiness_checks", {})
    failed_readiness = [
        key for key, value in readiness.items() if value is not True
    ]
    if failed_readiness:
        errors.append("Readiness checks failed: " + ", ".join(failed_readiness))

    checklist_text = ""
    if paths["checklist"].exists():
        checklist_text = paths["checklist"].read_text(encoding="utf-8")
        if "[x]" in checklist_text.lower():
            errors.append(
                "Submission checklist must remain unchecked during packaging."
            )

    expected_manifest_artifacts = {
        "submission_resume_pdf": "submission/resume.pdf",
        "submission_cover_letter_pdf": "submission/cover_letter.pdf",
        "application_package_json": "submission/application_package.json",
        "application_package_markdown": "submission/application_package.md",
        "submission_checklist": "submission/submission_checklist.md",
    }
    manifest_artifacts = manifest.get("artifacts", {})
    for key, expected in expected_manifest_artifacts.items():
        if manifest_artifacts.get(key) != expected:
            errors.append(f"Manifest artifact path mismatch for {key}.")

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Application package validation passed.")
    print(f"Application: {manifest['company']} - {manifest['role']}")
    print(f"Package version: v{package['package_version']}")
    print(f"Resume pages: {page_counts['resume']}")
    print(f"Cover letter pages: {page_counts['cover_letter']}")
    print("File identity: verified")
    print(f"Package path: {submission}")
    print(f"Manifest status: {manifest['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

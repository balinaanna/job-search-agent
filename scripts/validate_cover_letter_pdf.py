#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
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


def normalize(text: str) -> str:
    text = re.sub(r"[*_#>`]", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_pdf_text(path: Path) -> tuple[str, int]:
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text, len(reader.pages)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path.home()
        / ".hermes/skills/cover-letter-pdf-renderer/references/"
        / "cover-letter-pdf-release-schema.json",
    )
    args = parser.parse_args()
    workspace = args.workspace

    paths = {
        "manifest": workspace / "application_manifest.json",
        "source": workspace / "final_cover_letter.md",
        "finalization": workspace / "cover_letter_finalization.json",
        "pdf": workspace / "final_cover_letter.pdf",
        "release": workspace / "cover_letter_pdf_release.json",
        "release_md": workspace / "cover_letter_pdf_release.md",
    }

    try:
        manifest = load_json(paths["manifest"])
        finalization = load_json(paths["finalization"])
        release = load_json(paths["release"])
        schema = load_json(args.schema)
        source_text = paths["source"].read_text(encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []

    for error in Draft202012Validator(schema).iter_errors(release):
        loc = ".".join(str(p) for p in error.path) or "<root>"
        errors.append(f"schema {loc}: {error.message}")

    app_id = manifest.get("application_id")
    if release.get("application_id") != app_id:
        errors.append("Release application ID does not match manifest.")
    if finalization.get("application_id") != app_id:
        errors.append("Finalization application ID does not match manifest.")
    if release.get("company") != manifest.get("company"):
        errors.append("Release company does not match manifest.")
    if release.get("role") != manifest.get("role"):
        errors.append("Release role does not match manifest.")
    if manifest.get("status") != "cover_letter_rendered":
        errors.append("Manifest status must be cover_letter_rendered.")
    if finalization.get("manifest_status") != "cover_letter_ready":
        errors.append("Finalization must be in cover_letter_ready state.")

    if not paths["pdf"].exists():
        errors.append("Missing final_cover_letter.pdf.")
        pdf_text, page_count = "", 0
    else:
        try:
            pdf_text, page_count = extract_pdf_text(paths["pdf"])
        except Exception as exc:
            errors.append(f"Could not read PDF: {exc}")
            pdf_text, page_count = "", 0

    if release.get("page_count") != page_count:
        errors.append("Release page count does not match PDF.")

    version = release.get("version")
    expected_version_path = workspace / "versions" / f"final_cover_letter_v{version}.pdf"
    artifacts = release.get("artifacts", {})
    expected_artifacts = {
        "final_cover_letter_markdown": "final_cover_letter.md",
        "cover_letter_finalization": "cover_letter_finalization.json",
        "final_cover_letter_pdf": "final_cover_letter.pdf",
        "versioned_cover_letter_pdf": f"versions/final_cover_letter_v{version}.pdf",
    }
    for key, expected in expected_artifacts.items():
        if artifacts.get(key) != expected:
            errors.append(f"Artifact path mismatch for {key}.")

    hashes = release.get("hashes", {})
    hash_targets = {
        "final_cover_letter_markdown_sha256": paths["source"],
        "cover_letter_finalization_sha256": paths["finalization"],
        "final_cover_letter_pdf_sha256": paths["pdf"],
        "versioned_cover_letter_pdf_sha256": expected_version_path,
    }
    for key, path in hash_targets.items():
        if not path.exists():
            errors.append(f"Missing hashed artifact: {path}")
            continue
        actual = sha256_file(path)
        if hashes.get(key) != actual:
            errors.append(f"Hash mismatch for {key}.")

    if paths["pdf"].exists() and expected_version_path.exists():
        if sha256_file(paths["pdf"]) != sha256_file(expected_version_path):
            errors.append("Versioned PDF is not identical to final PDF.")

    finalization_source_hash = (
        finalization.get("release_hashes", {})
        .get("final_cover_letter_sha256")
    )
    actual_source_hash = sha256_file(paths["source"])
    if finalization_source_hash != actual_source_hash:
        errors.append("Source Markdown hash does not match finalization.")

    if normalize(source_text) != normalize(pdf_text):
        errors.append("Normalized PDF text does not match source Markdown.")

    text_verification = release.get("text_verification", {})
    if any(value is not True for value in text_verification.values()):
        errors.append("Text verification flags are incomplete.")

    visual = release.get("visual_inspection", {})
    visual_flags = [
        "completed",
        "no_clipping",
        "no_overlap",
        "no_broken_glyphs",
        "no_black_boxes",
        "margins_consistent",
        "readability_passed",
    ]
    failed_visual = [key for key in visual_flags if visual.get(key) is not True]
    if failed_visual:
        errors.append("Visual inspection failed: " + ", ".join(failed_visual))
    if visual.get("pages_inspected") != page_count:
        errors.append("Visual pages inspected does not match PDF page count.")

    checks = release.get("release_checks", {})
    failed_checks = [key for key, value in checks.items() if value is not True]
    if failed_checks:
        errors.append("Release checks failed: " + ", ".join(failed_checks))

    if not paths["release_md"].exists():
        errors.append("Missing cover_letter_pdf_release.md.")

    render_dir = workspace / ".cover_letter_pdf_render"
    if render_dir.exists():
        errors.append(
            "Temporary render directory still exists; remove it before release."
        )

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Cover letter PDF validation passed.")
    print(f"Application: {manifest['company']} - {manifest['role']}")
    print(f"Version: v{version}")
    print(f"Pages: {page_count}")
    print(f"Text match: verified")
    print(f"Visual inspection: passed")
    print(f"PDF SHA256: {hashes['final_cover_letter_pdf_sha256']}")
    print(f"Manifest status: {manifest['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

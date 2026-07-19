#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

try:
    from pypdf import PdfReader
except ImportError:
    raise SystemExit(
        "Missing dependency: pypdf\n"
        "Run: pip install pypdf"
    )


def load_json(path: Path) -> dict:
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


def normalize_markdown(text: str) -> str:
    lines: list[str] = []

    for line in text.splitlines():
        line = re.sub(
            r"^#{1,6}\s+",
            "",
            line.strip(),
        )
        line = re.sub(r"^[-*]\s+", "", line)
        line = line.replace("**", "").replace("*", "")

        if line:
            lines.append(line)

    value = " ".join(lines)

    value = (
        value
        .replace("–", "-")
        .replace("—", "-")
        .replace("’", "'")
    )

    return re.sub(r"\s+", " ", value).strip().lower()


def normalize_pdf_text(text: str) -> str:
    value = text.replace("•", " ")

    value = (
        value
        .replace("–", "-")
        .replace("—", "-")
        .replace("’", "'")
    )

    return re.sub(r"\s+", " ", value).strip().lower()


def compact(text: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        text.lower(),
    )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "workspace",
        type=Path,
    )

    parser.add_argument(
        "--schema",
        type=Path,
        default=(
            Path.home()
            / ".hermes/skills/resume-pdf-renderer/"
            / "references/resume-pdf-release-schema.json"
        ),
    )

    parser.add_argument(
        "--visual-inspection-passed",
        action="store_true",
    )

    parser.add_argument(
        "--no-clipping",
        action="store_true",
    )

    parser.add_argument(
        "--no-overlaps",
        action="store_true",
    )

    parser.add_argument(
        "--no-broken-glyphs",
        action="store_true",
    )

    args = parser.parse_args()

    workspace = args.workspace

    manifest_path = (
        workspace
        / "application_manifest.json"
    )

    source_path = (
        workspace
        / "final_resume.md"
    )

    finalization_path = (
        workspace
        / "resume_finalization.json"
    )

    pdf_path = (
        workspace
        / "final_resume.pdf"
    )

    release_path = (
        workspace
        / "resume_pdf_release.json"
    )

    release_md_path = (
        workspace
        / "resume_pdf_release.md"
    )

    try:
        manifest = load_json(manifest_path)
        finalization = load_json(finalization_path)
        release = load_json(release_path)
        schema = load_json(args.schema)

    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1

    errors: list[str] = []

    application_id = manifest.get(
        "application_id"
    )

    company = manifest.get("company")
    role = manifest.get("role")

    final_version = finalization.get(
        "final_version"
    )

    snapshot_path = (
        workspace
        / "versions"
        / f"final_resume_v{final_version}.pdf"
    )

    # Application identity

    if release.get("application_id") != application_id:
        errors.append(
            "Release application ID does not match manifest."
        )

    if release.get("company") != company:
        errors.append(
            "Release company does not match manifest."
        )

    if release.get("role") != role:
        errors.append(
            "Release role does not match manifest."
        )

    if finalization.get("application_id") != application_id:
        errors.append(
            "Finalization application ID does not match manifest."
        )

    if release.get("final_version") != final_version:
        errors.append(
            "Release final version does not match finalization."
        )

    # Workflow state

    current_manifest_status = manifest.get("status")

    allowed_manifest_statuses = {
        "ready",
        "rendered",
        "cover_letter_planned",
        "cover_letter_written",
        "cover_letter_reviewed",
        "cover_letter_revised",
        "cover_letter_ready",
        "cover_letter_rendered",
        "application_packaged",
    }

    if current_manifest_status not in allowed_manifest_statuses:
        errors.append(
            "Manifest status is not compatible with resume PDF validation: "
            f"{current_manifest_status!r}."
        )

    if finalization.get("manifest_status") != "ready":
        errors.append(
            "Finalization manifest status must be ready."
        )

    # Required artifacts

    for path in [
        source_path,
        finalization_path,
        pdf_path,
        snapshot_path,
        release_path,
        release_md_path,
    ]:
        if not path.exists():
            errors.append(
                f"Missing file: {path}"
            )

    # Artifact paths recorded in the release

    artifacts = release.get(
        "artifacts",
        {},
    )

    expected_artifacts = {
        "final_resume_markdown": (
            "final_resume.md"
        ),
        "resume_finalization": (
            "resume_finalization.json"
        ),
        "final_resume_pdf": (
            "final_resume.pdf"
        ),
        "versioned_resume_pdf": (
            f"versions/final_resume_v"
            f"{final_version}.pdf"
        ),
    }

    for key, expected in expected_artifacts.items():
        actual = artifacts.get(key)

        if actual != expected:
            errors.append(
                f"Release artifact path mismatch for "
                f"{key}: expected {expected}, "
                f"got {actual}."
            )

    hashes = release.get(
        "hashes",
        {},
    )

    # Source Markdown hash

    if source_path.exists():
        source_hash = sha256(source_path)

        finalization_source_hash = (
            finalization
            .get("hashes", {})
            .get("final_resume_sha256")
        )

        release_source_hash = hashes.get(
            "final_resume_markdown_sha256"
        )

        if source_hash != finalization_source_hash:
            errors.append(
                "Source Markdown hash does not match "
                "finalization."
            )

        if source_hash != release_source_hash:
            errors.append(
                "Source Markdown hash does not match "
                "PDF release."
            )

    # Finalization JSON hash

    if finalization_path.exists():
        actual_finalization_hash = sha256(
            finalization_path
        )

        recorded_finalization_hash = hashes.get(
            "resume_finalization_sha256"
        )

        if (
            actual_finalization_hash
            != recorded_finalization_hash
        ):
            errors.append(
                "Resume finalization hash does not match "
                "PDF release."
            )

    # PDF and snapshot hashes

    if pdf_path.exists() and snapshot_path.exists():
        pdf_hash = sha256(pdf_path)
        snapshot_hash = sha256(snapshot_path)

        recorded_pdf_hash = hashes.get(
            "final_resume_pdf_sha256"
        )

        recorded_snapshot_hash = hashes.get(
            "versioned_resume_pdf_sha256"
        )

        if pdf_hash != snapshot_hash:
            errors.append(
                "PDF snapshot differs from final PDF."
            )

        if pdf_hash != recorded_pdf_hash:
            errors.append(
                "Final PDF hash does not match release."
            )

        if snapshot_hash != recorded_snapshot_hash:
            errors.append(
                "Versioned PDF hash does not match release."
            )

        # PDF readability and page count

        try:
            reader = PdfReader(str(pdf_path))
            page_count = len(reader.pages)

        except Exception as exc:
            errors.append(
                f"Could not read final PDF: {exc}"
            )
            reader = None
            page_count = 0

        if (
            release
            .get("pdf", {})
            .get("page_count")
            != page_count
        ):
            errors.append(
                f"Recorded page count should be "
                f"{page_count}."
            )

        # Text fidelity

        if reader is not None:
            extracted = " ".join(
                page.extract_text() or ""
                for page in reader.pages
            )

            expected_text = normalize_markdown(
                source_path.read_text(
                    encoding="utf-8"
                )
            )

            actual_text = normalize_pdf_text(
                extracted
            )

            if compact(expected_text) != compact(actual_text):
                expected_compact = compact(
                    expected_text
                )

                actual_compact = compact(
                    actual_text
                )

                missing_ratio = 1 - (
                    len(actual_compact)
                    / max(
                        len(expected_compact),
                        1,
                    )
                )

                errors.append(
                    "Extracted PDF text differs from "
                    "normalized Markdown "
                    f"(length delta ratio "
                    f"{missing_ratio:.3f})."
                )

    if errors:
        print("Validation failed:")

        for error in errors:
            print(f"- {error}")

        return 1

    # Update validation flags only after textual and hash
    # validation has passed.

    validation = release.setdefault(
        "validation",
        {},
    )

    validation[
        "finalization_valid"
    ] = True

    validation[
        "source_hash_matches_finalization"
    ] = True

    validation[
        "pdf_snapshot_matches"
    ] = True

    validation[
        "text_fidelity_passed"
    ] = True

    validation[
        "visual_inspection_passed"
    ] = args.visual_inspection_passed

    validation[
        "no_clipping"
    ] = args.no_clipping

    validation[
        "no_overlaps"
    ] = args.no_overlaps

    validation[
        "no_broken_glyphs"
    ] = args.no_broken_glyphs

    visual_flags_passed = all([
        args.visual_inspection_passed,
        args.no_clipping,
        args.no_overlaps,
        args.no_broken_glyphs,
    ])

    if not visual_flags_passed:
        release_path.write_text(
            json.dumps(
                release,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        print(
            "Text validation passed, but visual "
            "inspection flags are incomplete."
        )

        print(
            "Inspect all rendered PNG pages, "
            "then rerun with:"
        )

        print(
            "  --visual-inspection-passed "
            "--no-clipping "
            "--no-overlaps "
            "--no-broken-glyphs"
        )

        return 2

    # Final manifest and release state

    if current_manifest_status == "ready":
        manifest["status"] = "rendered"
    else:
        # Preserve any valid downstream workflow status.
        manifest["status"] = current_manifest_status

    manifest_artifacts = manifest.setdefault(
        "artifacts",
        {},
    )

    manifest_artifacts[
        "final_resume_pdf"
    ] = "final_resume.pdf"

    manifest_artifacts[
        "resume_pdf_release_json"
    ] = "resume_pdf_release.json"

    manifest_artifacts[
        "resume_pdf_release_markdown"
    ] = "resume_pdf_release.md"

    release["manifest_status"] = "rendered"

    # Validate final release schema

    for schema_error in (
        Draft202012Validator(schema)
        .iter_errors(release)
    ):
        location = ".".join(
            str(part)
            for part in schema_error.path
        ) or "<root>"

        errors.append(
            f"schema {location}: "
            f"{schema_error.message}"
        )

    if errors:
        print("Validation failed:")

        for error in errors:
            print(f"- {error}")

        return 1

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    release_path.write_text(
        json.dumps(
            release,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    release_md_path.write_text(
        f"""# Resume PDF Release

## Result

PDF rendering and validation passed.

## Application

- {company} — {role}
- Application ID: `{application_id}`

## Version

- Final version: {final_version}

## Artifacts

- PDF: `final_resume.pdf`
- Snapshot: `versions/final_resume_v{final_version}.pdf`

## PDF

- Pages: {release['pdf']['page_count']}
- Page size: LETTER
- Renderer: ReportLab
- Font: Helvetica
- Layout: single column

## Validation

- Source finalization: passed
- Source hash: matched
- PDF snapshot: matched
- Text fidelity: passed
- Visual inspection: passed
- Clipping: none observed
- Overlaps: none observed
- Broken glyphs: none observed

## Workflow State

- Resume PDF release status: rendered
- Current application manifest status: {manifest['status']}

## Next Step

Continue with the cover-letter planner,
application-answer planner, or
application-package assembler.
""",
        encoding="utf-8",
    )

    print("Resume PDF validation passed.")
    print(
        f"Application: {company} — {role}"
    )
    print(
        f"Final version: {final_version}"
    )
    print(
        f"Pages: {release['pdf']['page_count']}"
    )
    print(
        f"PDF: {pdf_path}"
    )
    print(
        "PDF SHA256: "
        f"{release['hashes']['final_resume_pdf_sha256']}"
    )
    print(
        f"Manifest status: {manifest['status']}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

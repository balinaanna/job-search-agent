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
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^#{1,6}\s+", "", line.strip())
        line = re.sub(r"^[-*]\s+", "", line)
        line = line.replace("**", "").replace("*", "")
        if line:
            lines.append(line)
    value = " ".join(lines)
    value = value.replace("–", "-").replace("—", "-").replace("’", "'")
    return re.sub(r"\s+", " ", value).strip().lower()


def normalize_pdf_text(text: str) -> str:
    value = text.replace("•", " ")
    value = value.replace("–", "-").replace("—", "-").replace("’", "'")
    return re.sub(r"\s+", " ", value).strip().lower()


def compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path.home()
        / ".hermes/skills/resume-pdf-renderer/references/resume-pdf-release-schema.json",
    )
    parser.add_argument("--visual-inspection-passed", action="store_true")
    parser.add_argument("--no-clipping", action="store_true")
    parser.add_argument("--no-overlaps", action="store_true")
    parser.add_argument("--no-broken-glyphs", action="store_true")
    args = parser.parse_args()

    workspace = args.workspace
    manifest_path = workspace / "application_manifest.json"
    source_path = workspace / "final_resume.md"
    finalization_path = workspace / "resume_finalization.json"
    pdf_path = workspace / "final_resume.pdf"
    release_path = workspace / "resume_pdf_release.json"
    release_md_path = workspace / "resume_pdf_release.md"

    try:
        manifest = load_json(manifest_path)
        finalization = load_json(finalization_path)
        release = load_json(release_path)
        schema = load_json(args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []

    final_version = finalization.get("final_version")
    snapshot_path = workspace / f"versions/final_resume_v{final_version}.pdf"

    if release.get("application_id") != manifest.get("application_id"):
        errors.append("Release application ID does not match manifest.")
    if finalization.get("application_id") != manifest.get("application_id"):
        errors.append("Finalization application ID does not match manifest.")
    if release.get("final_version") != final_version:
        errors.append("Release final version does not match finalization.")

    if manifest.get("status") not in {"ready", "rendered"}:
        errors.append("Manifest status must be ready or rendered during PDF validation.")
    if finalization.get("manifest_status") != "ready":
        errors.append("Finalization manifest status must be ready.")

    for path in [source_path, pdf_path, snapshot_path, release_md_path]:
        if not path.exists():
            errors.append(f"Missing file: {path}")

    if source_path.exists():
        source_hash = sha256(source_path)
        if source_hash != finalization.get("hashes", {}).get("final_resume_sha256"):
            errors.append("Source Markdown hash does not match finalization.")
        if source_hash != release.get("hashes", {}).get("source_markdown_sha256"):
            errors.append("Source Markdown hash does not match PDF release.")

    if pdf_path.exists() and snapshot_path.exists():
        pdf_hash = sha256(pdf_path)
        snapshot_hash = sha256(snapshot_path)
        if pdf_hash != snapshot_hash:
            errors.append("PDF snapshot differs from final PDF.")
        if pdf_hash != release.get("hashes", {}).get("pdf_sha256"):
            errors.append("Final PDF hash does not match release.")
        if snapshot_hash != release.get("hashes", {}).get("snapshot_pdf_sha256"):
            errors.append("Snapshot PDF hash does not match release.")

        reader = PdfReader(str(pdf_path))
        page_count = len(reader.pages)
        if release.get("pdf", {}).get("page_count") != page_count:
            errors.append(f"Recorded page count should be {page_count}.")

        extracted = " ".join(page.extract_text() or "" for page in reader.pages)
        expected_text = normalize_markdown(source_path.read_text(encoding="utf-8"))
        actual_text = normalize_pdf_text(extracted)

        if compact(expected_text) != compact(actual_text):
            expected_compact = compact(expected_text)
            actual_compact = compact(actual_text)
            missing_ratio = 1 - (len(actual_compact) / max(len(expected_compact), 1))
            errors.append(
                "Extracted PDF text differs from normalized Markdown "
                f"(length delta ratio {missing_ratio:.3f})."
            )

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    release["validation"]["text_fidelity_passed"] = True
    release["validation"]["visual_inspection_passed"] = args.visual_inspection_passed
    release["validation"]["no_clipping"] = args.no_clipping
    release["validation"]["no_overlaps"] = args.no_overlaps
    release["validation"]["no_broken_glyphs"] = args.no_broken_glyphs

    if not all([
        args.visual_inspection_passed,
        args.no_clipping,
        args.no_overlaps,
        args.no_broken_glyphs,
    ]):
        print("Text validation passed, but visual inspection flags are incomplete.")
        print("Inspect all rendered PNG pages, then rerun with:")
        print(
            "  --visual-inspection-passed --no-clipping "
            "--no-overlaps --no-broken-glyphs"
        )
        return 2

    manifest["status"] = "rendered"
    artifacts = manifest.setdefault("artifacts", {})
    artifacts["final_resume_pdf"] = str(pdf_path)
    artifacts["resume_pdf_release_json"] = str(release_path)
    artifacts["resume_pdf_release_markdown"] = str(release_md_path)

    release["manifest_status"] = "rendered"

    for error in Draft202012Validator(schema).iter_errors(release):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"schema {location}: {error.message}")

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    release_path.write_text(json.dumps(release, indent=2), encoding="utf-8")

    release_md_path.write_text(
        f"""# Resume PDF Release

## Result

PDF rendering and validation passed.

## Application

- {manifest.get('company')} — {manifest.get('role')}
- Application ID: `{manifest.get('application_id')}`

## Version

- Final version: {final_version}

## Artifacts

- PDF: `{pdf_path}`
- Snapshot: `{snapshot_path}`

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

## Manifest

- Status: rendered

## Next Step

Continue with the cover-letter planner, application-answer planner, or
application-package validator.
""",
        encoding="utf-8",
    )

    print("Resume PDF validation passed.")
    print(f"Application: {manifest['company']} — {manifest['role']}")
    print(f"Final version: {final_version}")
    print(f"Pages: {release['pdf']['page_count']}")
    print(f"PDF: {pdf_path}")
    print(f"Manifest status: {manifest['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

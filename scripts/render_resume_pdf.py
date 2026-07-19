#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

try:
    from pypdf import PdfReader
except ImportError:
    raise SystemExit(
        "Missing dependency: pypdf\n"
        "Run: pip install pypdf"
    )
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
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


def inline_markup(text: str) -> str:
    text = escape(text.strip())
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(.+?)\*(?!\*)", r"<i>\1</i>", text)
    text = text.replace(" | ", " &nbsp;|&nbsp; ")
    return text


def parse_markdown(path: Path) -> list[tuple[str, str]]:
    elements: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip():
            elements.append(("blank", ""))
        elif line.startswith("# "):
            elements.append(("name", line[2:].strip()))
        elif line.startswith("## "):
            elements.append(("section", line[3:].strip()))
        elif line.startswith("### "):
            elements.append(("subheading", line[4:].strip()))
        elif re.match(r"^\s*[-*]\s+", line):
            elements.append(("bullet", re.sub(r"^\s*[-*]\s+", "", line).strip()))
        else:
            elements.append(("paragraph", line.strip()))
    return elements


def build_pdf(source: Path, destination: Path, settings: dict) -> None:
    body_size = settings["body_font_size"]
    doc = SimpleDocTemplate(
        str(destination),
        pagesize=LETTER,
        leftMargin=settings["left_margin_inches"] * inch,
        rightMargin=settings["right_margin_inches"] * inch,
        topMargin=settings["top_margin_inches"] * inch,
        bottomMargin=settings["bottom_margin_inches"] * inch,
        title="Resume",
        author="",
        creator="Resume PDF Renderer",
        subject="Resume",
    )

    name_style = ParagraphStyle(
        "Name",
        fontName="Helvetica-Bold",
        fontSize=settings["name_font_size"],
        leading=settings["name_font_size"] + 2,
        alignment=TA_CENTER,
        spaceAfter=3,
    )
    contact_style = ParagraphStyle(
        "Contact",
        fontName="Helvetica",
        fontSize=settings["contact_font_size"],
        leading=settings["contact_font_size"] + 1.5,
        alignment=TA_CENTER,
        spaceAfter=5,
    )
    section_style = ParagraphStyle(
        "Section",
        fontName="Helvetica-Bold",
        fontSize=settings["heading_font_size"],
        leading=settings["heading_font_size"] + 1.5,
        alignment=TA_LEFT,
        spaceBefore=5,
        spaceAfter=2,
        borderWidth=0,
    )
    subheading_style = ParagraphStyle(
        "Subheading",
        fontName="Helvetica-Bold",
        fontSize=body_size,
        leading=body_size + 1.5,
        alignment=TA_LEFT,
        spaceBefore=2.5,
        spaceAfter=0.5,
    )
    body_style = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=body_size,
        leading=body_size + 1.6,
        alignment=TA_LEFT,
        spaceAfter=1.6,
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        parent=body_style,
        leftIndent=10,
        firstLineIndent=0,
        spaceAfter=1.4,
    )

    story = []
    parsed = parse_markdown(source)
    first_paragraph_after_name = True
    bullet_buffer: list[str] = []

    def flush_bullets() -> None:
        nonlocal bullet_buffer
        if not bullet_buffer:
            return
        items = [
            ListItem(
                Paragraph(inline_markup(item), bullet_style),
                leftIndent=9,
            )
            for item in bullet_buffer
        ]
        story.append(
            ListFlowable(
                items,
                bulletType="bullet",
                start="circle",
                leftIndent=10,
                bulletFontName="Helvetica",
                bulletFontSize=5,
                bulletOffsetY=1.5,
                spaceAfter=1.5,
            )
        )
        bullet_buffer = []

    for kind, text in parsed:
        if kind != "bullet":
            flush_bullets()

        if kind == "blank":
            story.append(Spacer(1, 1.5))
        elif kind == "name":
            story.append(Paragraph(inline_markup(text), name_style))
        elif kind == "section":
            story.append(Paragraph(inline_markup(text.upper()), section_style))
            first_paragraph_after_name = False
        elif kind == "subheading":
            story.append(Paragraph(inline_markup(text), subheading_style))
            first_paragraph_after_name = False
        elif kind == "bullet":
            bullet_buffer.append(text)
            first_paragraph_after_name = False
        elif kind == "paragraph":
            style = contact_style if first_paragraph_after_name else body_style
            story.append(Paragraph(inline_markup(text), style))
            first_paragraph_after_name = False

    flush_bullets()
    doc.build(story)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()

    workspace = args.workspace
    manifest_path = workspace / "application_manifest.json"
    finalization_path = workspace / "resume_finalization.json"
    source_path = workspace / "final_resume.md"
    output_path = workspace / "final_resume.pdf"
    release_path = workspace / "resume_pdf_release.json"
    release_md_path = workspace / "resume_pdf_release.md"
    versions_dir = workspace / "versions"

    manifest = load_json(manifest_path)
    finalization = load_json(finalization_path)

    if manifest.get("status") != "ready":
        raise SystemExit("Manifest status must be ready before PDF rendering.")
    if finalization.get("manifest_status") != "ready":
        raise SystemExit("Finalization record is not ready.")

    final_version = finalization["final_version"]
    expected_source_hash = finalization["hashes"]["final_resume_sha256"]
    actual_source_hash = sha256(source_path)
    if expected_source_hash != actual_source_hash:
        raise SystemExit("final_resume.md hash does not match finalization record.")

    versions_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = versions_dir / f"final_resume_v{final_version}.pdf"
    if snapshot_path.exists():
        raise SystemExit(f"Refusing to overwrite existing snapshot: {snapshot_path}")

    settings = {
        "font_family": "Helvetica",
        "name_font_size": 16,
        "contact_font_size": 9,
        "heading_font_size": 10.5,
        "body_font_size": 9.25,
        "left_margin_inches": 0.55,
        "right_margin_inches": 0.55,
        "top_margin_inches": 0.45,
        "bottom_margin_inches": 0.45,
        "single_column": True,
    }

    build_pdf(source_path, output_path, settings)
    shutil.copy2(output_path, snapshot_path)

    reader = PdfReader(str(output_path))
    page_count = len(reader.pages)

    application_id = manifest.get("application_id")
    company = manifest.get("company")
    role = manifest.get("role")

    if not application_id:
        raise ValueError("Manifest is missing application_id.")

    if not company:
        raise ValueError("Manifest is missing company.")

    if not role:
        raise ValueError("Manifest is missing role.")

    release = {
        "application_id": application_id,
        "company": company,
        "role": role,
        "final_version": final_version,
        "artifacts": {
            "final_resume_markdown": "final_resume.md",
            "resume_finalization": "resume_finalization.json",
            "final_resume_pdf": "final_resume.pdf",
            "versioned_resume_pdf": (
                f"versions/final_resume_v{final_version}.pdf"
            ),
        },
        "hashes": {
            "final_resume_markdown_sha256": sha256(
                workspace / "final_resume.md"
            ),
            "resume_finalization_sha256": sha256(
                workspace / "resume_finalization.json"
            ),
            "final_resume_pdf_sha256": sha256(
                workspace / "final_resume.pdf"
            ),
            "versioned_resume_pdf_sha256": sha256(
                workspace
                / "versions"
                / f"final_resume_v{final_version}.pdf"
            ),
        },
        "source": {
            "markdown_path": str(source_path),
            "finalization_path": str(finalization_path),
        },
        "outputs": {
            "pdf_path": str(output_path),
            "snapshot_pdf_path": str(snapshot_path),
            "release_markdown_path": str(release_md_path),
        },
        "pdf": {
            "page_count": page_count,
            "page_size": "LETTER",
            "renderer": "reportlab",
        },
        "layout": settings,
        "validation": {
            "finalization_valid": True,
            "source_hash_matches_finalization": True,
            "pdf_snapshot_matches": sha256(output_path) == sha256(snapshot_path),
            "text_fidelity_passed": False,
            "visual_inspection_passed": False,
            "no_clipping": False,
            "no_overlaps": False,
            "no_broken_glyphs": False,
        },
        "manifest_status": "ready",
        "next_permitted_workflows": [
            "cover-letter-planner",
            "application-answer-planner",
            "application-package-validator",
        ],
    }
    release_path.write_text(json.dumps(release, indent=2), encoding="utf-8")

    summary = f"""# Resume PDF Release

## Result

PDF rendered. Text and visual validation are still required.

## Application

- {manifest.get('company')} — {manifest.get('role')}
- Application ID: `{manifest.get('application_id')}`

## Version

- Final version: {final_version}

## Artifacts

- PDF: `{output_path}`
- Snapshot: `{snapshot_path}`

## Page Count

- {page_count}

## Validation Status

- Finalization valid: yes
- Source hash matches: yes
- PDF snapshot matches: yes
- Text fidelity: pending
- Visual inspection: pending
- Manifest status: ready
"""
    release_md_path.write_text(summary, encoding="utf-8")

    print("Resume PDF rendered.")
    print(f"PDF: {output_path}")
    print(f"Snapshot: {snapshot_path}")
    print(f"Pages: {page_count}")
    print("Run validate_resume_pdf.py after visual inspection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

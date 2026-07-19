#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def markdown_to_blocks(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def clean_inline_markdown(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)
    text = re.sub(r"^\s*#{1,6}\s+", "", text)
    text = text.replace("\n", "<br/>")
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--font", default="Helvetica")
    parser.add_argument("--font-size", type=float, default=10.8)
    parser.add_argument("--leading", type=float, default=15.0)
    args = parser.parse_args()

    workspace = args.workspace
    source = workspace / "final_cover_letter.md"
    output = workspace / "final_cover_letter.pdf"

    if not source.exists():
        print(f"ERROR: missing {source}", file=sys.stderr)
        return 1

    text = source.read_text(encoding="utf-8")
    blocks = markdown_to_blocks(text)
    if not blocks:
        print("ERROR: final_cover_letter.md is empty.", file=sys.stderr)
        return 1

    style = ParagraphStyle(
        name="CoverLetterBody",
        fontName=args.font,
        fontSize=args.font_size,
        leading=args.leading,
        alignment=TA_LEFT,
        spaceAfter=0,
        splitLongWords=False,
        allowWidows=0,
        allowOrphans=0,
    )

    story = []
    for index, block in enumerate(blocks):
        story.append(Paragraph(clean_inline_markdown(block), style))
        if index < len(blocks) - 1:
            story.append(Spacer(1, 0.16 * inch))

    doc = SimpleDocTemplate(
        str(output),
        pagesize=LETTER,
        leftMargin=0.8 * inch,
        rightMargin=0.8 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="Cover Letter",
        author="Anna Stupachenko",
        subject="Job Application Cover Letter",
    )
    doc.build(story)

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

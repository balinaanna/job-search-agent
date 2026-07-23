from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from resume_format import date_range, humanize_group, merge_skill_groups, sort_recent_first, training_suffix


ROOT = Path(__file__).resolve().parent.parent


def text(value: object) -> str:
    return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(output: Path, data: dict) -> Path:
    career = data["career"]; skills = data["skills"]; technologies = data["technologies"]
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Name", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=colors.HexColor("#163d2e"), alignment=TA_CENTER, spaceAfter=5))
    styles.add(ParagraphStyle(name="Contact", parent=styles["Normal"], fontSize=8.5, leading=12, textColor=colors.HexColor("#52605a"), alignment=TA_CENTER, spaceAfter=12))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#1f6f52"), spaceBefore=11, spaceAfter=6))
    styles.add(ParagraphStyle(name="Role", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=9.5, leading=12, spaceAfter=2))
    styles.add(ParagraphStyle(name="Meta", parent=styles["Normal"], fontSize=8, leading=11, textColor=colors.HexColor("#67736e"), spaceAfter=4))
    styles.add(ParagraphStyle(name="BodySmall", parent=styles["Normal"], fontSize=8.5, leading=12, spaceAfter=4))
    styles.add(ParagraphStyle(name="Inventory", parent=styles["Normal"], fontSize=7.6, leading=9.6, spaceAfter=4))
    styles.add(ParagraphStyle(name="BulletSmall", parent=styles["Normal"], fontSize=8.2, leading=11.5, leftIndent=10, firstLineIndent=-6, bulletIndent=0, spaceAfter=2))
    contact = career["contact"]; candidate = career["candidate"]
    story = [Paragraph(text(candidate["name"]), styles["Name"]), Paragraph(" | ".join(text(contact.get(key)) for key in ("location", "email", "phone", "linkedin") if contact.get(key)), styles["Contact"])]
    story += [Paragraph("PROFESSIONAL SUMMARY", styles["Section"]), Paragraph(text(career["career_summary"]["positioning"]), styles["BodySmall"])]
    story.append(Paragraph("SKILLS", styles["Section"]))
    for group, items in merge_skill_groups(skills, technologies):
        story += [Paragraph(text(humanize_group(group)), styles["Role"]), Paragraph(", ".join(text(item.get("name")) for item in items), styles["Inventory"])]
    story.append(Paragraph("EDUCATION", styles["Section"]))
    for item in sort_recent_first(career.get("education", [])):
        story.append(Paragraph(f"<b>{text(item.get('credential'))}, {text(item.get('field'))}</b> - {text(item.get('institution'))} ({text(date_range(item.get('dates', {})))})", styles["BodySmall"]))
    story.append(Paragraph("CERTIFICATIONS", styles["Section"]))
    for item in sort_recent_first(career.get("training_and_certifications", [])):
        story.append(Paragraph(f"<b>{text(item.get('name'))}</b>{text(training_suffix(item))}", styles["BodySmall"]))
    story.append(Paragraph("WORK EXPERIENCE", styles["Section"]))
    for role in career.get("employment", []):
        date_label = date_range(role.get("dates", {}))
        story += [Paragraph(f"{text(role.get('official_title'))} | {text(role.get('organization'))}", styles["Role"]), Paragraph(" | ".join(value for value in (text(role.get("location")), text(role.get("engagement_type")), text(date_label)) if value), styles["Meta"]), Paragraph(text(role.get("summary")), styles["BodySmall"])]
        story += [Paragraph(text(item), styles["BulletSmall"], bulletText="-") for item in role.get("accomplishments", [])]
        story.append(Spacer(1, 5))
    story.append(Paragraph("PROJECTS", styles["Section"]))
    for project in career.get("projects", []):
        role = project.get("role")
        heading = f"{text(project.get('name'))} | {text(role)}" if role else text(project.get("name"))
        date_label = date_range(project.get("dates", {}))
        meta = " | ".join(value for value in (text(project.get("type")), text(project.get("organization")), text(project.get("status")), text(date_label)) if value)
        story += [Paragraph(heading, styles["Role"]), Paragraph(meta, styles["Meta"]), Paragraph(text(project.get("summary")), styles["BodySmall"])]
        if project.get("url"):
            story.append(Paragraph(text(project["url"]), styles["Meta"]))
        story += [Paragraph(text(item), styles["BulletSmall"], bulletText="-") for item in project.get("highlights", [])]
        story.append(Spacer(1, 4))
    doc = SimpleDocTemplate(str(output), pagesize=letter, rightMargin=.65*inch, leftMargin=.65*inch, topMargin=.55*inch, bottomMargin=.55*inch, title="Anna Stupachenko - Master Resume")
    doc.build(story)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--data", type=Path, required=True); args = parser.parse_args()
    path = render(ROOT / "output/pdf/Anna_Stupachenko_Master_Resume.pdf", json.loads(args.data.read_text(encoding="utf-8")))
    print(path.relative_to(ROOT))

#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from validate_job_lead import (
    JobLeadValidationError,
    load_json,
    validate_business_rules,
    validate_schema,
)


DEFAULT_LEADS_DIRECTORY = Path("data/job-leads")
DEFAULT_SCHEMA_PATH = Path(
    "hermes-skills/job-discovery/references/job-lead-schema.json"
)


def load_leads(directory: Path) -> list[dict[str, Any]]:
    if not directory.exists():
        raise JobLeadValidationError(
            f"Leads directory does not exist: {directory}"
        )

    return [load_json(path) for path in sorted(directory.glob("*.json"))]


def validate_leads(
    leads: list[dict[str, Any]],
    schema: dict[str, Any],
) -> None:
    for lead in leads:
        errors = validate_schema(lead, schema)
        errors.extend(validate_business_rules(lead))
        if errors:
            lead_id = lead.get("lead_id", "<unknown>")
            details = "\n".join(f"- {error}" for error in errors)
            raise JobLeadValidationError(
                f"Invalid Job Lead {lead_id}:\n{details}"
            )


def lead_bucket(lead: dict[str, Any]) -> str:
    status = lead["status"]["lead_status"]
    discovery = lead["discovery"]

    if status == "archived":
        return "archived"
    if discovery["hard_filter_result"] == "manual_review":
        return "manual_review"
    if discovery["hard_filter_result"] == "not_evaluated":
        return "unprocessed"
    if discovery["hard_filter_result"] == "fail" or status == "rejected":
        return "rejected"
    if discovery["preliminary_score"] is None:
        return "unprocessed"
    if discovery["full_analysis_recommended"] is True:
        return "full_analysis"
    return "discovery_only"


def ranking_key(lead: dict[str, Any]) -> tuple[int, str, str]:
    score = lead["discovery"]["preliminary_score"]
    return (
        -(score if score is not None else -1),
        lead["identity"]["normalized_company"],
        lead["identity"]["normalized_role"],
    )


def location_label(lead: dict[str, Any]) -> str:
    location = lead["location"]
    parts = [
        location.get("city"),
        location.get("region"),
        location.get("country"),
    ]
    place = ", ".join(str(part) for part in parts if part)
    workplace = location["workplace_type"].replace("_", " ").title()
    return f"{workplace}; {place or location['raw']}"


def salary_label(lead: dict[str, Any]) -> str | None:
    salary = lead["employment"]["salary"]
    minimum = salary.get("minimum")
    maximum = salary.get("maximum")
    currency = salary.get("currency")
    period = salary.get("period")

    if minimum is None and maximum is None:
        return None

    def amount(value: Any) -> str:
        return f"{value:,.0f}" if isinstance(value, (int, float)) else str(value)

    if minimum is not None and maximum is not None:
        value = f"{amount(minimum)}–{amount(maximum)}"
    elif minimum is not None:
        value = f"from {amount(minimum)}"
    else:
        value = f"up to {amount(maximum)}"

    suffix = f"/{period}" if period else ""
    return " ".join(part for part in (currency, f"{value}{suffix}") if part)


def strongest_components(lead: dict[str, Any]) -> str | None:
    components = lead["discovery"]["score_components"]
    populated = [
        (name, value)
        for name, value in components.items()
        if isinstance(value, int)
    ]
    if not populated:
        return None

    populated.sort(key=lambda item: (-item[1], item[0]))
    return ", ".join(
        f"{name.replace('_', ' ')} {value}"
        for name, value in populated[:3]
    )


def reason_lines(lead: dict[str, Any]) -> list[str]:
    reasons = list(lead["discovery"].get("hard_filter_reasons", []))
    reasons.extend(
        penalty["reason"]
        for penalty in lead["discovery"].get("penalties", [])
    )
    return reasons


def render_lead(lead: dict[str, Any], rank: int | None = None) -> list[str]:
    identity = lead["identity"]
    discovery = lead["discovery"]
    score = discovery["preliminary_score"]
    prefix = f"{rank}. " if rank is not None else "- "
    score_label = f" — {score}/100" if score is not None else ""
    lines = [
        f"{prefix}**{identity['role']} — {identity['company']}**{score_label}",
        f"   - Location: {location_label(lead)}",
        f"   - Source: {lead['source']['platform'].replace('_', ' ')}",
        f"   - Posting: {lead['source']['posting_url']}",
    ]

    salary = salary_label(lead)
    if salary:
        lines.append(f"   - Compensation: {salary}")
    if lead["application"].get("posted_date"):
        lines.append(
            f"   - Posted: {lead['application']['posted_date']}"
        )

    strengths = strongest_components(lead)
    if strengths:
        lines.append(f"   - Strongest preliminary signals: {strengths}")

    for reason in reason_lines(lead):
        lines.append(f"   - Review note: {reason}")

    return lines


SECTION_LABELS = {
    "full_analysis": "Recommended for Full Job Fit Analysis",
    "manual_review": "Manual Eligibility Review",
    "discovery_only": "Discovery Only",
    "rejected": "Rejected by Discovery Rules",
    "unprocessed": "Needs Discovery Processing",
    "archived": "Archived Duplicates",
}


def render_shortlist(leads: list[dict[str, Any]]) -> str:
    buckets: dict[str, list[dict[str, Any]]] = {
        name: [] for name in SECTION_LABELS
    }
    for lead in leads:
        buckets[lead_bucket(lead)].append(lead)
    for bucket in buckets.values():
        bucket.sort(key=ranking_key)

    counts = Counter(lead_bucket(lead) for lead in leads)
    lines = [
        "# Job Lead Shortlist",
        "",
        "## Summary",
        "",
        f"- Total leads: {len(leads)}",
        f"- Recommended for full analysis: {counts['full_analysis']}",
        f"- Manual eligibility review: {counts['manual_review']}",
        f"- Discovery only: {counts['discovery_only']}",
        f"- Rejected: {counts['rejected']}",
        f"- Needs processing: {counts['unprocessed']}",
        f"- Archived duplicates: {counts['archived']}",
    ]

    for bucket_name, heading in SECTION_LABELS.items():
        lines.extend(["", f"## {heading}", ""])
        bucket = buckets[bucket_name]
        if not bucket:
            lines.append("None.")
            continue
        for index, lead in enumerate(bucket, start=1):
            rank = index if bucket_name == "full_analysis" else None
            lines.extend(render_lead(lead, rank=rank))
            lines.append("")
        if lines[-1] == "":
            lines.pop()

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a human-readable shortlist from Job Lead files."
    )
    parser.add_argument(
        "--leads-directory",
        type=Path,
        default=DEFAULT_LEADS_DIRECTORY,
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        leads = load_leads(args.leads_directory)
        schema = load_json(args.schema)
        validate_leads(leads, schema)
        report = render_shortlist(leads)

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report, encoding="utf-8")
            print(f"Wrote Job Lead shortlist to {args.output}.")
        else:
            print(report, end="")
        return 0
    except JobLeadValidationError as exc:
        print(f"Shortlist generation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

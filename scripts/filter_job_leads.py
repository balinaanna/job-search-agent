#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from validate_job_lead import (
    JobLeadValidationError,
    load_json,
    validate_business_rules,
    validate_schema,
)


DEFAULT_LEADS_DIRECTORY = Path("data/job-leads")
DEFAULT_CRITERIA_PATH = Path("strategy/job_search_criteria.json")
DEFAULT_SCHEMA_PATH = Path(
    "hermes-skills/job-discovery/references/job-lead-schema.json"
)

LOWER_MAINLAND_CITIES = {
    "abbotsford",
    "anmore",
    "belcarra",
    "burnaby",
    "coquitlam",
    "delta",
    "langley",
    "lions bay",
    "maple ridge",
    "new westminster",
    "north vancouver",
    "pitt meadows",
    "port coquitlam",
    "port moody",
    "richmond",
    "surrey",
    "vancouver",
    "west vancouver",
    "white rock",
}


@dataclass(frozen=True)
class FilterDecision:
    result: str
    reasons: tuple[str, ...]


def normalized_text(value: str) -> str:
    return " ".join(value.casefold().replace("-", " ").split())


def contains_phrase(text: str, phrase: str) -> bool:
    normalized = normalized_text(text)
    target = normalized_text(phrase)
    return re.search(
        rf"(?<!\w){re.escape(target)}(?!\w)",
        normalized,
    ) is not None


def is_excluded_title(
    lead: dict[str, Any],
    criteria: dict[str, Any],
) -> bool:
    title = lead["position"]["title"]
    excluded = criteria["search_strategy"]["excluded_titles"]
    return any(contains_phrase(title, value) for value in excluded)


def outside_lower_mainland(location: dict[str, Any]) -> bool | None:
    country = location.get("country")
    region = location.get("region")
    city = location.get("city")

    if country and normalized_text(country) != "canada":
        return True

    if region and normalized_text(region) != "british columbia":
        return True

    if city:
        return normalized_text(city) not in LOWER_MAINLAND_CITIES

    if region and normalized_text(region) == "british columbia":
        return None

    return None


def text_evidence(lead: dict[str, Any]) -> str:
    values = (
        lead["identity"]["role"],
        lead["employment"].get("schedule") or "",
        lead["content"]["description_text"],
    )
    return normalized_text(" ".join(values))


def evaluate_hard_filters(
    lead: dict[str, Any],
    criteria: dict[str, Any],
) -> FilterDecision:
    failures: list[str] = []
    uncertainties: list[str] = []
    location = lead["location"]
    requirements = lead["requirements"]
    employment = lead["employment"]
    application = lead["application"]
    hard_filters = criteria["hard_filters"]
    text = text_evidence(lead)

    if application["posting_status"] in {"closed", "expired"}:
        failures.append(
            f"Posting status is {application['posting_status']}."
        )

    if is_excluded_title(lead, criteria):
        failures.append("The job title is explicitly excluded.")

    if hard_filters["must_hire_in_canada"]:
        can_hire = location.get("can_hire_in_canada")
        if can_hire is False:
            failures.append("The employer cannot hire in Canada.")
        elif can_hire is None:
            uncertainties.append(
                "Canadian hiring eligibility is not confirmed."
            )

    if location.get("relocation_required") is True:
        failures.append("The role requires relocation.")

    if (
        location["workplace_type"] == "on_site"
        and not hard_filters["daily_on_site_required"]
    ):
        outside = outside_lower_mainland(location)
        if outside is True:
            failures.append(
                "The role requires on-site work outside the Lower Mainland."
            )
        elif outside is None:
            uncertainties.append(
                "The on-site location is not precise enough to confirm eligibility."
            )

    driving = requirements.get("driving_required")
    if driving is True and not hard_filters["driving_required"]:
        failures.append("The role requires driving.")

    clearance = requirements.get("clearance_required")
    if (
        clearance is True
        and not hard_filters["security_clearance_not_currently_held"]
    ):
        failures.append(
            "The role requires a security clearance not currently held."
        )

    if employment["employment_type"] == "volunteer":
        failures.append("The role is unpaid or volunteer work.")
    elif re.search(r"\b(unpaid|volunteer position)\b", text):
        failures.append("The posting identifies the role as unpaid.")

    commission_only_patterns = (
        "commission only",
        "commission based only",
        "100% commission",
        "solely commission",
    )
    if any(phrase in text for phrase in commission_only_patterns):
        failures.append("Compensation is commission-only.")

    if employment["employment_type"] == "part_time":
        hours = re.search(
            r"\b(\d{1,2})\s*(?:hours|hrs)\s*(?:per|a)\s*week\b",
            text,
        )
        if hours and int(hours.group(1)) < 25:
            failures.append("The role is part-time under 25 hours per week.")
        else:
            uncertainties.append(
                "Part-time weekly hours are not confirmed as 25 or more."
            )

    if failures:
        return FilterDecision("fail", tuple(failures))

    if uncertainties:
        return FilterDecision("manual_review", tuple(uncertainties))

    return FilterDecision("pass", ())


def apply_filter_decision(
    lead: dict[str, Any],
    decision: FilterDecision,
) -> None:
    protected_statuses = {
        "shortlisted",
        "analysis_started",
        "analysis_completed",
        "application_started",
        "applied",
        "closed",
        "archived",
    }
    existing_status = lead["status"]["lead_status"]
    lead["discovery"]["hard_filter_result"] = decision.result
    lead["discovery"]["hard_filter_reasons"] = list(decision.reasons)

    if decision.result == "fail":
        lead["discovery"]["full_analysis_recommended"] = False
        lead["status"]["lead_status"] = "rejected"
    elif decision.result == "pass":
        lead["discovery"]["full_analysis_recommended"] = None
        lead["status"]["lead_status"] = "eligible"
    else:
        lead["discovery"]["full_analysis_recommended"] = None
        lead["status"]["lead_status"] = "new"

    if existing_status in protected_statuses:
        lead["status"]["lead_status"] = existing_status


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_lead_files(
    leads_directory: Path,
) -> list[tuple[Path, dict[str, Any]]]:
    if not leads_directory.exists():
        raise JobLeadValidationError(
            f"Leads directory does not exist: {leads_directory}"
        )
    return [
        (path, load_json(path))
        for path in sorted(leads_directory.glob("*.json"))
    ]


def validate_lead(
    lead: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    errors = validate_schema(lead, schema)
    errors.extend(validate_business_rules(lead))
    return errors


def filter_leads(
    leads: list[tuple[Path, dict[str, Any]]],
    criteria: dict[str, Any],
    dry_run: bool = False,
) -> list[tuple[str, FilterDecision]]:
    decisions: list[tuple[str, FilterDecision]] = []

    for path, lead in leads:
        if lead["status"]["lead_status"] == "archived":
            continue

        decision = evaluate_hard_filters(lead, criteria)
        decisions.append((lead["lead_id"], decision))

        if not dry_run:
            apply_filter_decision(lead, decision)
            write_json(path, lead)

    return decisions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply deterministic hard eligibility filters to normalized, "
            "deduplicated Job Leads."
        )
    )
    parser.add_argument(
        "--leads-directory",
        type=Path,
        default=DEFAULT_LEADS_DIRECTORY,
    )
    parser.add_argument(
        "--criteria",
        type=Path,
        default=DEFAULT_CRITERIA_PATH,
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        criteria = load_json(args.criteria)
        schema = load_json(args.schema)
        leads = load_lead_files(args.leads_directory)

        if not leads:
            print(f"No Job Lead files found in {args.leads_directory}.")
            return 0

        errors: list[str] = []
        for path, lead in leads:
            errors.extend(
                f"{path}: {error}"
                for error in validate_lead(lead, schema)
            )

        if errors:
            print(
                "Filtering stopped because Job Lead validation failed:",
                file=sys.stderr,
            )
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1

        decisions = filter_leads(leads, criteria, args.dry_run)

        if not args.dry_run:
            for path, lead in load_lead_files(args.leads_directory):
                post_errors = validate_lead(lead, schema)
                if post_errors:
                    print(
                        f"Filtering produced an invalid Job Lead: {path}",
                        file=sys.stderr,
                    )
                    for error in post_errors:
                        print(f"- {error}", file=sys.stderr)
                    return 1

        counts = {"pass": 0, "fail": 0, "manual_review": 0}
        for _, decision in decisions:
            counts[decision.result] += 1

        print(f"Evaluated {len(decisions)} active Job Lead(s).")
        print(
            f"Pass: {counts['pass']}; fail: {counts['fail']}; "
            f"manual review: {counts['manual_review']}."
        )
        for lead_id, decision in decisions:
            reason_text = "; ".join(decision.reasons) or "No hard-filter failures."
            print(f"- {lead_id}: {decision.result} — {reason_text}")

        if args.dry_run:
            print("Dry run: no Job Lead files were modified.")

        return 0
    except JobLeadValidationError as exc:
        print(f"Filtering failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

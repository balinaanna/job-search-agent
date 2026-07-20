#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
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


@dataclass(frozen=True)
class DuplicateMatch:
    canonical_lead_id: str
    duplicate_lead_id: str
    confidence: str
    reason: str
    score: float


def normalized_similarity(first: str, second: str) -> float:
    return SequenceMatcher(
        None,
        first.casefold().strip(),
        second.casefold().strip(),
    ).ratio()


def description_similarity(
    first: dict[str, Any],
    second: dict[str, Any],
) -> float:
    first_text = first["content"]["description_text"]
    second_text = second["content"]["description_text"]

    return normalized_similarity(first_text, second_text)


def same_company(
    first: dict[str, Any],
    second: dict[str, Any],
) -> bool:
    return (
        first["identity"]["normalized_company"]
        == second["identity"]["normalized_company"]
    )


def same_external_job_id(
    first: dict[str, Any],
    second: dict[str, Any],
) -> bool:
    first_id = first["identity"].get("external_job_id")
    second_id = second["identity"].get("external_job_id")

    return (
        bool(first_id)
        and bool(second_id)
        and first_id == second_id
    )


def same_canonical_url(
    first: dict[str, Any],
    second: dict[str, Any],
) -> bool:
    return (
        first["source"]["canonical_url"]
        == second["source"]["canonical_url"]
    )


def same_description_hash(
    first: dict[str, Any],
    second: dict[str, Any],
) -> bool:
    return (
        first["content"]["description_hash"]
        == second["content"]["description_hash"]
    )


def locations_compatible(
    first: dict[str, Any],
    second: dict[str, Any],
) -> bool:
    first_location = first["location"]
    second_location = second["location"]

    def raw_signature(location: dict[str, Any]) -> tuple[str, ...]:
        raw = str(location.get("raw") or "").casefold()
        tokens = re.findall(r"[a-z0-9]+", raw)
        return tuple(sorted(token for token in tokens if token != "unspecified"))

    first_raw = raw_signature(first_location)
    second_raw = raw_signature(second_location)
    if first_raw and second_raw and first_raw != second_raw:
        return False

    first_country = first_location.get("country")
    second_country = second_location.get("country")

    if (
        first_country is not None
        and second_country is not None
        and first_country != second_country
    ):
        return False

    first_city = first_location.get("city")
    second_city = second_location.get("city")

    if (
        first_city is not None
        and second_city is not None
        and first_city != second_city
    ):
        return False

    first_workplace = first_location.get("workplace_type")
    second_workplace = second_location.get("workplace_type")

    incompatible_workplace_pairs = {
        ("remote", "on_site"),
        ("on_site", "remote"),
    }

    if (
        first_workplace,
        second_workplace,
    ) in incompatible_workplace_pairs:
        return False

    return True


def source_priority(lead: dict[str, Any]) -> int:
    platform = lead["source"]["platform"]

    priorities = {
        "company_careers": 100,
        "greenhouse": 95,
        "lever": 95,
        "ashby": 95,
        "workday": 95,
        "government_board": 85,
        "referral": 80,
        "recruiter": 75,
        "linkedin": 70,
        "indeed": 65,
        "other": 50,
    }

    return priorities.get(platform, 0)


def completeness_score(lead: dict[str, Any]) -> int:
    score = 0

    if lead["identity"].get("external_job_id"):
        score += 5

    if lead["position"].get("department"):
        score += 2

    if lead["location"].get("country"):
        score += 2

    if lead["location"].get("city"):
        score += 1

    if lead["location"].get("can_hire_in_canada") is not None:
        score += 3

    if lead["application"].get("posted_date"):
        score += 2

    if lead["application"].get("deadline"):
        score += 1

    salary = lead["employment"]["salary"]

    if salary.get("minimum") is not None:
        score += 2

    if salary.get("maximum") is not None:
        score += 2

    score += min(
        len(lead["requirements"].get("technical_skills", [])),
        5,
    )

    score += min(
        len(lead["content"].get("responsibilities", [])),
        3,
    )

    return score


def collected_timestamp(lead: dict[str, Any]) -> datetime:
    value = lead["source"]["collected_at"]

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.max.astimezone()


def choose_canonical(
    first: dict[str, Any],
    second: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    workflow_priority = {
        "applied": 1000,
        "application_started": 900,
        "analysis_completed": 800,
        "analysis_started": 700,
        "shortlisted": 600,
        "eligible": 100,
        "new": 50,
        "rejected": 20,
        "closed": 10,
        "archived": 0,
    }
    first_rank = (
        workflow_priority.get(first["status"]["lead_status"], 0),
        source_priority(first),
        completeness_score(first),
        -collected_timestamp(first).timestamp(),
    )

    second_rank = (
        workflow_priority.get(second["status"]["lead_status"], 0),
        source_priority(second),
        completeness_score(second),
        -collected_timestamp(second).timestamp(),
    )

    if first_rank >= second_rank:
        return first, second

    return second, first


def detect_duplicate(
    first: dict[str, Any],
    second: dict[str, Any],
) -> DuplicateMatch | None:
    if first["lead_id"] == second["lead_id"]:
        return None

    company_matches = same_company(first, second)

    if same_canonical_url(first, second):
        canonical, duplicate = choose_canonical(first, second)

        return DuplicateMatch(
            canonical_lead_id=canonical["lead_id"],
            duplicate_lead_id=duplicate["lead_id"],
            confidence="exact",
            reason="Canonical posting URLs match.",
            score=1.0,
        )

    if company_matches and same_external_job_id(first, second):
        canonical, duplicate = choose_canonical(first, second)

        return DuplicateMatch(
            canonical_lead_id=canonical["lead_id"],
            duplicate_lead_id=duplicate["lead_id"],
            confidence="exact",
            reason=(
                "Normalized company and external job ID match."
            ),
            score=1.0,
        )

    if (
        company_matches
        and same_description_hash(first, second)
        and normalized_similarity(
            first["identity"]["normalized_role"],
            second["identity"]["normalized_role"],
        ) >= 0.92
        and locations_compatible(first, second)
    ):
        canonical, duplicate = choose_canonical(first, second)

        return DuplicateMatch(
            canonical_lead_id=canonical["lead_id"],
            duplicate_lead_id=duplicate["lead_id"],
            confidence="exact",
            reason=(
                "Normalized company and description hash match."
            ),
            score=1.0,
        )

    if not company_matches:
        return None

    role_similarity = normalized_similarity(
        first["identity"]["normalized_role"],
        second["identity"]["normalized_role"],
    )

    if role_similarity < 0.82:
        return None

    text_similarity = description_similarity(first, second)

    if (
        role_similarity >= 0.92
        and text_similarity >= 0.90
        and locations_compatible(first, second)
    ):
        canonical, duplicate = choose_canonical(first, second)

        combined_score = (
            role_similarity * 0.4
            + text_similarity * 0.6
        )

        return DuplicateMatch(
            canonical_lead_id=canonical["lead_id"],
            duplicate_lead_id=duplicate["lead_id"],
            confidence="strong",
            reason=(
                "Company matches and role, location, and "
                "description are strongly similar."
            ),
            score=round(combined_score, 4),
        )

    if (
        role_similarity >= 0.82
        and text_similarity >= 0.65
        and locations_compatible(first, second)
    ):
        canonical, duplicate = choose_canonical(first, second)

        combined_score = (
            role_similarity * 0.5
            + text_similarity * 0.5
        )

        return DuplicateMatch(
            canonical_lead_id=canonical["lead_id"],
            duplicate_lead_id=duplicate["lead_id"],
            confidence="possible",
            reason=(
                "Company matches and the role and description "
                "are similar enough to require review."
            ),
            score=round(combined_score, 4),
        )

    return None


def is_duplicate_candidate(
    first: dict[str, Any],
    second: dict[str, Any],
) -> bool:
    return (
        same_company(first, second)
        or same_canonical_url(first, second)
    )


def load_lead_files(
    leads_directory: Path,
) -> list[tuple[Path, dict[str, Any]]]:
    if not leads_directory.exists():
        raise JobLeadValidationError(
            f"Leads directory does not exist: {leads_directory}"
        )

    results: list[tuple[Path, dict[str, Any]]] = []

    for path in sorted(leads_directory.glob("*.json")):
        results.append((path, load_json(path)))

    return results


def append_unique_note(
    lead: dict[str, Any],
    note: str,
) -> None:
    notes = lead["status"].setdefault("notes", [])

    if note not in notes:
        notes.append(note)


def archive_duplicate(
    duplicate: dict[str, Any],
    match: DuplicateMatch,
) -> None:
    duplicate["status"]["lead_status"] = "archived"
    duplicate["status"]["duplicate_of"] = (
        match.canonical_lead_id
    )

    append_unique_note(
        duplicate,
        (
            f"Deduplicated automatically: {match.reason} "
            f"Confidence={match.confidence}; "
            f"score={match.score:.4f}."
        ),
    )


def mark_possible_duplicate(
    lead: dict[str, Any],
    other_lead_id: str,
    match: DuplicateMatch,
) -> None:
    append_unique_note(
        lead,
        (
            f"Possible duplicate of {other_lead_id}: "
            f"{match.reason} Score={match.score:.4f}. "
            "Manual review required."
        ),
    )


def write_json(
    path: Path,
    value: dict[str, Any],
) -> None:
    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def validate_all_leads(
    leads: list[tuple[Path, dict[str, Any]]],
    schema: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    for path, lead in leads:
        lead_errors = validate_schema(lead, schema)
        lead_errors.extend(validate_business_rules(lead))

        for error in lead_errors:
            errors.append(f"{path}: {error}")

    return errors


def deduplicate(
    leads: list[tuple[Path, dict[str, Any]]],
) -> list[DuplicateMatch]:
    matches: list[DuplicateMatch] = []

    leads_by_id = {
        lead["lead_id"]: (path, lead)
        for path, lead in leads
    }

    lead_values = list(leads_by_id.values())

    for first_index in range(len(lead_values)):
        first_path, first = lead_values[first_index]

        if first["status"]["duplicate_of"] is not None:
            continue

        for second_index in range(
            first_index + 1,
            len(lead_values),
        ):
            second_path, second = lead_values[second_index]

            if second["status"]["duplicate_of"] is not None:
                continue

            if not is_duplicate_candidate(first, second):
                continue

            match = detect_duplicate(first, second)

            if match is None:
                continue

            matches.append(match)

            canonical_path, canonical = leads_by_id[
                match.canonical_lead_id
            ]

            duplicate_path, duplicate = leads_by_id[
                match.duplicate_lead_id
            ]

            if match.confidence in {"exact", "strong"}:
                archive_duplicate(duplicate, match)

                if duplicate["source"]["platform"] != (
                    canonical["source"]["platform"]
                ):
                    append_unique_note(
                        canonical,
                        (
                            "Also discovered through "
                            f"{duplicate['source']['platform']} at "
                            f"{duplicate['source']['posting_url']}."
                        ),
                    )

                write_json(duplicate_path, duplicate)
                write_json(canonical_path, canonical)

            elif match.confidence == "possible":
                mark_possible_duplicate(
                    canonical,
                    duplicate["lead_id"],
                    match,
                )
                mark_possible_duplicate(
                    duplicate,
                    canonical["lead_id"],
                    match,
                )

                write_json(canonical_path, canonical)
                write_json(duplicate_path, duplicate)

    return matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect duplicate normalized Job Leads and archive "
            "high-confidence duplicates."
        )
    )

    parser.add_argument(
        "--leads-directory",
        type=Path,
        default=DEFAULT_LEADS_DIRECTORY,
        help=(
            "Directory containing normalized Job Lead JSON files. "
            f"Defaults to {DEFAULT_LEADS_DIRECTORY}."
        ),
    )

    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help=(
            "Path to job-lead-schema.json. "
            f"Defaults to {DEFAULT_SCHEMA_PATH}."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Report duplicate matches without modifying lead files."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        schema = load_json(args.schema)
        leads = load_lead_files(args.leads_directory)

        if not leads:
            print(
                f"No Job Lead files found in {args.leads_directory}."
            )
            return 0

        validation_errors = validate_all_leads(
            leads,
            schema,
        )

        if validation_errors:
            print(
                "Deduplication stopped because Job Lead "
                "validation failed:",
                file=sys.stderr,
            )

            for error in validation_errors:
                print(f"- {error}", file=sys.stderr)

            return 1

        if args.dry_run:
            matches: list[DuplicateMatch] = []

            for first_index in range(len(leads)):
                _, first = leads[first_index]

                for second_index in range(
                    first_index + 1,
                    len(leads),
                ):
                    _, second = leads[second_index]

                    if not is_duplicate_candidate(first, second):
                        continue

                    match = detect_duplicate(first, second)

                    if match is not None:
                        matches.append(match)
        else:
            matches = deduplicate(leads)

            updated_leads = load_lead_files(
                args.leads_directory
            )

            post_validation_errors = validate_all_leads(
                updated_leads,
                schema,
            )

            if post_validation_errors:
                print(
                    "Deduplication produced invalid Job Leads:",
                    file=sys.stderr,
                )

                for error in post_validation_errors:
                    print(f"- {error}", file=sys.stderr)

                return 1

        exact_count = sum(
            match.confidence == "exact"
            for match in matches
        )
        strong_count = sum(
            match.confidence == "strong"
            for match in matches
        )
        possible_count = sum(
            match.confidence == "possible"
            for match in matches
        )

        print("Job Lead deduplication completed.")
        print(f"Leads examined: {len(leads)}")
        print(f"Exact duplicates: {exact_count}")
        print(f"Strong duplicates: {strong_count}")
        print(f"Possible duplicates: {possible_count}")

        for match in matches:
            print(
                f"- [{match.confidence}] "
                f"{match.duplicate_lead_id} → "
                f"{match.canonical_lead_id}: "
                f"{match.reason}"
            )

        if args.dry_run:
            print("Dry run: no files were changed.")

        return 0

    except JobLeadValidationError as exc:
        print(f"Deduplication failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

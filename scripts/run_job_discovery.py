#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collect_job_postings import (
    CollectionError,
    collect_source,
    load_sources,
    write_postings,
)
from deduplicate_job_leads import deduplicate, load_lead_files
from filter_job_leads import filter_leads
from normalize_job_lead import build_job_lead, strategy_version
from score_job_leads import score_leads
from surface_job_leads import render_shortlist
from validate_job_lead import (
    JobLeadValidationError,
    load_json,
    validate_business_rules,
    validate_schema,
)


DEFAULT_SOURCES_PATH = Path("strategy/job_sources.json")
DEFAULT_RAW_DIRECTORY = Path("data/raw-job-postings")
DEFAULT_LEADS_DIRECTORY = Path("data/job-leads")
DEFAULT_SHORTLIST_PATH = Path("data/job-leads/shortlist.md")
DEFAULT_CRITERIA_PATH = Path("strategy/job_search_criteria.json")
DEFAULT_SCHEMA_PATH = Path(
    "hermes-skills/job-discovery/references/job-lead-schema.json"
)


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def refreshed_lead(
    existing: dict[str, Any],
    fresh: dict[str, Any],
) -> dict[str, Any]:
    fresh["source"]["first_seen_at"] = (
        existing["source"].get("first_seen_at")
        or existing["source"]["collected_at"]
    )
    fresh["status"] = existing["status"]
    return fresh


def normalize_raw_directory(
    raw_directory: Path,
    leads_directory: Path,
    criteria_path: Path,
    schema: dict[str, Any],
) -> tuple[int, int]:
    if not raw_directory.exists():
        raise JobLeadValidationError(
            f"Raw posting directory does not exist: {raw_directory}"
        )
    criteria_version = strategy_version(criteria_path)
    created = 0
    refreshed = 0

    for raw_path in sorted(raw_directory.glob("*.json")):
        lead = build_job_lead(load_json(raw_path), criteria_version)
        output_path = leads_directory / f"{lead['lead_id']}.json"
        if output_path.exists():
            lead = refreshed_lead(load_json(output_path), lead)
            refreshed += 1
        else:
            created += 1

        errors = validate_schema(lead, schema)
        errors.extend(validate_business_rules(lead))
        if errors:
            details = "\n".join(f"- {error}" for error in errors)
            raise JobLeadValidationError(
                f"Normalization failed for {raw_path}:\n{details}"
            )
        write_json(output_path, lead)

    return created, refreshed


def validate_all(
    leads: list[tuple[Path, dict[str, Any]]],
    schema: dict[str, Any],
) -> None:
    errors: list[str] = []
    for path, lead in leads:
        lead_errors = validate_schema(lead, schema)
        lead_errors.extend(validate_business_rules(lead))
        errors.extend(f"{path}: {error}" for error in lead_errors)
    if errors:
        raise JobLeadValidationError("\n".join(errors))


def run_pipeline(
    raw_directory: Path,
    leads_directory: Path,
    shortlist_path: Path,
    criteria_path: Path,
    schema_path: Path,
) -> dict[str, int]:
    criteria = load_json(criteria_path)
    schema = load_json(schema_path)
    created, refreshed = normalize_raw_directory(
        raw_directory,
        leads_directory,
        criteria_path,
        schema,
    )

    leads = load_lead_files(leads_directory)
    validate_all(leads, schema)
    matches = deduplicate(leads)

    leads = load_lead_files(leads_directory)
    filter_results = filter_leads(leads, criteria)

    leads = load_lead_files(leads_directory)
    score_results = score_leads(leads, criteria)

    leads = load_lead_files(leads_directory)
    validate_all(leads, schema)
    shortlist_path.parent.mkdir(parents=True, exist_ok=True)
    shortlist_path.write_text(
        render_shortlist([lead for _, lead in leads]),
        encoding="utf-8",
    )

    return {
        "created": created,
        "refreshed": refreshed,
        "duplicates": len(matches),
        "filtered": len(filter_results),
        "scored": len(score_results),
        "full_analysis": sum(
            result.full_analysis_recommended for _, result in score_results
        ),
    }


def collect_configured_sources(
    sources_path: Path,
    raw_directory: Path,
) -> tuple[int, int, int]:
    sources = load_sources(sources_path)
    collected_at = datetime.now(timezone.utc).isoformat()
    postings: list[dict[str, Any]] = []
    for source in sources:
        postings.extend(collect_source(source, collected_at))
    created, updated = write_postings(postings, raw_directory)
    return len(postings), created, updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect, normalize, deduplicate, filter, score, and surface "
            "public job postings."
        )
    )
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES_PATH)
    parser.add_argument(
        "--raw-directory", type=Path, default=DEFAULT_RAW_DIRECTORY
    )
    parser.add_argument(
        "--leads-directory", type=Path, default=DEFAULT_LEADS_DIRECTORY
    )
    parser.add_argument("--shortlist", type=Path, default=DEFAULT_SHORTLIST_PATH)
    parser.add_argument("--criteria", type=Path, default=DEFAULT_CRITERIA_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument(
        "--skip-collection",
        action="store_true",
        help="Process raw posting files already on disk without network access.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if not args.skip_collection:
            total, created_raw, updated_raw = collect_configured_sources(
                args.sources,
                args.raw_directory,
            )
            print(
                f"Collection: {total} posting(s); "
                f"created {created_raw}, refreshed {updated_raw}."
            )

        summary = run_pipeline(
            args.raw_directory,
            args.leads_directory,
            args.shortlist,
            args.criteria,
            args.schema,
        )
        print(
            "Normalization: "
            f"created {summary['created']}, refreshed {summary['refreshed']}."
        )
        print(f"Duplicate matches: {summary['duplicates']}.")
        print(f"Hard-filtered active leads: {summary['filtered']}.")
        print(f"Scored active leads: {summary['scored']}.")
        print(
            "Recommended for full analysis: "
            f"{summary['full_analysis']}."
        )
        print(f"Shortlist: {args.shortlist}")
        return 0
    except (CollectionError, JobLeadValidationError) as exc:
        print(f"Job Discovery failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


DEFAULT_SCHEMA_PATH = Path(
    "hermes-skills/job-discovery/references/job-lead-schema.json"
)


class JobLeadValidationError(Exception):
    """Raised when a Job Lead cannot be loaded or validated."""


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise JobLeadValidationError(f"File does not exist: {path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise JobLeadValidationError(
            f"Invalid JSON in {path}: "
            f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(data, dict):
        raise JobLeadValidationError(
            f"Expected a JSON object at the root of {path}."
        )

    return data


def normalized_description_hash(description: str) -> str:
    normalized = " ".join(description.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_schema(
    lead: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )

    errors: list[str] = []

    for error in sorted(
        validator.iter_errors(lead),
        key=lambda item: list(item.absolute_path),
    ):
        path = ".".join(str(part) for part in error.absolute_path)

        if path:
            errors.append(f"{path}: {error.message}")
        else:
            errors.append(error.message)

    return errors


def validate_business_rules(lead: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    salary = lead["employment"]["salary"]
    salary_minimum = salary["minimum"]
    salary_maximum = salary["maximum"]

    if (
        salary_minimum is not None
        and salary_maximum is not None
        and salary_minimum > salary_maximum
    ):
        errors.append(
            "employment.salary.minimum cannot exceed "
            "employment.salary.maximum."
        )

    years_minimum = lead["requirements"]["years_experience_min"]
    years_maximum = lead["requirements"].get("years_experience_max")

    if (
        years_minimum is not None
        and years_maximum is not None
        and years_minimum > years_maximum
    ):
        errors.append(
            "requirements.years_experience_min cannot exceed "
            "requirements.years_experience_max."
        )

    description = lead["content"]["description_text"]
    stored_hash = lead["content"]["description_hash"]
    calculated_hash = normalized_description_hash(description)

    if stored_hash != calculated_hash:
        errors.append(
            "content.description_hash does not match the normalized "
            "description_text SHA-256 hash. "
            f"Expected: {calculated_hash}"
        )

    hard_filter_result = lead["discovery"]["hard_filter_result"]
    full_analysis_recommended = lead["discovery"][
        "full_analysis_recommended"
    ]

    if (
        hard_filter_result == "fail"
        and full_analysis_recommended is True
    ):
        errors.append(
            "discovery.full_analysis_recommended cannot be true when "
            "hard_filter_result is fail."
        )

    duplicate_of = lead["status"]["duplicate_of"]
    lead_status = lead["status"]["lead_status"]

    if duplicate_of is not None and lead_status != "archived":
        errors.append(
            "A duplicated lead should use lead_status archived."
        )

    if lead_status == "archived" and duplicate_of is None:
        notes = lead["status"].get("notes", [])

        if not notes:
            errors.append(
                "An archived non-duplicate lead must include a status note."
            )

    score = lead["discovery"]["preliminary_score"]
    components = lead["discovery"]["score_components"]

    populated_components = [
        value
        for value in components.values()
        if value is not None
    ]

    if score is not None and not populated_components:
        errors.append(
            "A preliminary score requires at least one populated "
            "score component."
        )

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a normalized Job Lead artifact."
    )

    parser.add_argument(
        "lead_path",
        type=Path,
        help="Path to the Job Lead JSON file.",
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

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        lead = load_json(args.lead_path)
        schema = load_json(args.schema)

        errors = validate_schema(lead, schema)
        errors.extend(validate_business_rules(lead))

        if errors:
            print("Job Lead validation failed:", file=sys.stderr)

            for error in errors:
                print(f"- {error}", file=sys.stderr)

            return 1

        print("Job Lead validation passed.")
        print(f"Lead ID: {lead['lead_id']}")
        print(
            "Opportunity: "
            f"{lead['identity']['company']} — "
            f"{lead['identity']['role']}"
        )
        print(
            "Source: "
            f"{lead['source']['platform']}"
        )
        print(
            "Preliminary score: "
            f"{lead['discovery']['preliminary_score']}"
        )
        print(
            "Hard filter: "
            f"{lead['discovery']['hard_filter_result']}"
        )
        print(
            "Full analysis recommended: "
            f"{lead['discovery']['full_analysis_recommended']}"
        )

        return 0

    except JobLeadValidationError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

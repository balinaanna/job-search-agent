#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_CRITERIA_PATH = Path("strategy/job_search_criteria.json")


class ValidationError(Exception):
    """Raised when the job search criteria contract is invalid."""


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValidationError(f"File does not exist: {path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}: "
            f"{exc.msg}"
        ) from exc

    if not isinstance(data, dict):
        raise ValidationError(
            f"Expected a JSON object at the root of {path}."
        )

    return data


def require_keys(
    value: dict[str, Any],
    required_keys: set[str],
    path: str,
) -> list[str]:
    errors: list[str] = []

    for key in sorted(required_keys):
        if key not in value:
            errors.append(f"{path}.{key} is required.")

    return errors


def validate_score(
    value: Any,
    path: str,
    minimum: int = 0,
    maximum: int = 100,
) -> list[str]:
    if isinstance(value, bool) or not isinstance(value, int):
        return [f"{path} must be an integer."]

    if value < minimum or value > maximum:
        return [
            f"{path} must be between {minimum} and {maximum}; "
            f"received {value}."
        ]

    return []


def validate_non_empty_string(value: Any, path: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{path} must be a non-empty string."]

    return []


def validate_unique_strings(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{path} must be an array."]

    errors: list[str] = []
    normalized: list[str] = []

    for index, item in enumerate(value):
        errors.extend(
            validate_non_empty_string(item, f"{path}[{index}]")
        )

        if isinstance(item, str) and item.strip():
            normalized.append(item.strip().casefold())

    if len(normalized) != len(set(normalized)):
        errors.append(f"{path} contains duplicate values.")

    return errors


def validate_target_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{path} must be an array."]

    errors: list[str] = []
    titles: list[str] = []

    for index, target in enumerate(value):
        item_path = f"{path}[{index}]"

        if not isinstance(target, dict):
            errors.append(f"{item_path} must be an object.")
            continue

        errors.extend(
            require_keys(
                target,
                {"title", "priority_score", "reasons"},
                item_path,
            )
        )

        if "title" in target:
            errors.extend(
                validate_non_empty_string(
                    target["title"],
                    f"{item_path}.title",
                )
            )
            if isinstance(target["title"], str):
                titles.append(target["title"].strip().casefold())

        if "priority_score" in target:
            errors.extend(
                validate_score(
                    target["priority_score"],
                    f"{item_path}.priority_score",
                )
            )

        if "reasons" in target:
            errors.extend(
                validate_unique_strings(
                    target["reasons"],
                    f"{item_path}.reasons",
                )
            )

    if len(titles) != len(set(titles)):
        errors.append(f"{path} contains duplicate target titles.")

    return errors


def validate_conditional_targets(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{path} must be an array."]

    errors: list[str] = []
    titles: list[str] = []

    for index, target in enumerate(value):
        item_path = f"{path}[{index}]"

        if not isinstance(target, dict):
            errors.append(f"{item_path} must be an object.")
            continue

        errors.extend(
            require_keys(
                target,
                {"title", "priority_score", "conditions"},
                item_path,
            )
        )

        if "title" in target:
            errors.extend(
                validate_non_empty_string(
                    target["title"],
                    f"{item_path}.title",
                )
            )
            if isinstance(target["title"], str):
                titles.append(target["title"].strip().casefold())

        if "priority_score" in target:
            errors.extend(
                validate_score(
                    target["priority_score"],
                    f"{item_path}.priority_score",
                )
            )

        if "conditions" in target:
            errors.extend(
                validate_unique_strings(
                    target["conditions"],
                    f"{item_path}.conditions",
                )
            )

    if len(titles) != len(set(titles)):
        errors.append(f"{path} contains duplicate target titles.")

    return errors


def validate_scored_preferences(
    value: Any,
    path: str,
) -> list[str]:
    if not isinstance(value, list):
        return [f"{path} must be an array."]

    errors: list[str] = []
    names: list[str] = []

    for index, preference in enumerate(value):
        item_path = f"{path}[{index}]"

        if not isinstance(preference, dict):
            errors.append(f"{item_path} must be an object.")
            continue

        errors.extend(
            require_keys(
                preference,
                {"name", "score"},
                item_path,
            )
        )

        if "name" in preference:
            errors.extend(
                validate_non_empty_string(
                    preference["name"],
                    f"{item_path}.name",
                )
            )
            if isinstance(preference["name"], str):
                names.append(preference["name"].strip().casefold())

        if "score" in preference:
            errors.extend(
                validate_score(
                    preference["score"],
                    f"{item_path}.score",
                )
            )

    if len(names) != len(set(names)):
        errors.append(f"{path} contains duplicate preference names.")

    return errors


def validate_criteria(criteria: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    errors.extend(
        require_keys(
            criteria,
            {
                "schema_version",
                "strategy_version",
                "candidate",
                "search_strategy",
                "locations",
                "employment",
                "company_preferences",
                "technical_focus",
                "customer_facing_preferences",
                "hard_filters",
                "ranking",
            },
            "criteria",
        )
    )

    if criteria.get("schema_version") != 1:
        errors.append("criteria.schema_version must equal 1.")

    errors.extend(
        validate_score(
            criteria.get("strategy_version"),
            "criteria.strategy_version",
            minimum=1,
            maximum=1_000_000,
        )
    )

    candidate = criteria.get("candidate")
    if isinstance(candidate, dict):
        errors.extend(
            require_keys(
                candidate,
                {"career_profile_path", "current_direction"},
                "criteria.candidate",
            )
        )

        if "career_profile_path" in candidate:
            errors.extend(
                validate_non_empty_string(
                    candidate["career_profile_path"],
                    "criteria.candidate.career_profile_path",
                )
            )

        if "current_direction" in candidate:
            errors.extend(
                validate_non_empty_string(
                    candidate["current_direction"],
                    "criteria.candidate.current_direction",
                )
            )
    elif candidate is not None:
        errors.append("criteria.candidate must be an object.")

    strategy = criteria.get("search_strategy")
    if isinstance(strategy, dict):
        errors.extend(
            require_keys(
                strategy,
                {
                    "primary_targets",
                    "secondary_targets",
                    "conditional_targets",
                    "excluded_titles",
                },
                "criteria.search_strategy",
            )
        )

        if "primary_targets" in strategy:
            errors.extend(
                validate_target_list(
                    strategy["primary_targets"],
                    "criteria.search_strategy.primary_targets",
                )
            )

        if "secondary_targets" in strategy:
            errors.extend(
                validate_target_list(
                    strategy["secondary_targets"],
                    "criteria.search_strategy.secondary_targets",
                )
            )

        if "conditional_targets" in strategy:
            errors.extend(
                validate_conditional_targets(
                    strategy["conditional_targets"],
                    "criteria.search_strategy.conditional_targets",
                )
            )

        if "excluded_titles" in strategy:
            errors.extend(
                validate_unique_strings(
                    strategy["excluded_titles"],
                    "criteria.search_strategy.excluded_titles",
                )
            )
    elif strategy is not None:
        errors.append("criteria.search_strategy must be an object.")

    company_preferences = criteria.get("company_preferences")
    if isinstance(company_preferences, dict):
        for section in (
            "preferred",
            "acceptable",
            "lower_priority",
        ):
            if section not in company_preferences:
                errors.append(
                    f"criteria.company_preferences.{section} is required."
                )
            else:
                errors.extend(
                    validate_scored_preferences(
                        company_preferences[section],
                        f"criteria.company_preferences.{section}",
                    )
                )

        if "excluded" not in company_preferences:
            errors.append(
                "criteria.company_preferences.excluded is required."
            )
        else:
            errors.extend(
                validate_unique_strings(
                    company_preferences["excluded"],
                    "criteria.company_preferences.excluded",
                )
            )
    elif company_preferences is not None:
        errors.append(
            "criteria.company_preferences must be an object."
        )

    technical_focus = criteria.get("technical_focus")
    if isinstance(technical_focus, dict):
        for section in (
            "high_priority",
            "medium_priority",
            "low_priority",
        ):
            if section not in technical_focus:
                errors.append(
                    f"criteria.technical_focus.{section} is required."
                )
            else:
                errors.extend(
                    validate_scored_preferences(
                        technical_focus[section],
                        f"criteria.technical_focus.{section}",
                    )
                )
    elif technical_focus is not None:
        errors.append("criteria.technical_focus must be an object.")

    ranking = criteria.get("ranking")
    if isinstance(ranking, dict):
        errors.extend(
            require_keys(
                ranking,
                {
                    "minimum_discovery_score",
                    "minimum_full_analysis_score",
                    "weights",
                    "penalties",
                },
                "criteria.ranking",
            )
        )

        for key in (
            "minimum_discovery_score",
            "minimum_full_analysis_score",
        ):
            if key in ranking:
                errors.extend(
                    validate_score(
                        ranking[key],
                        f"criteria.ranking.{key}",
                    )
                )

        weights = ranking.get("weights")
        if isinstance(weights, dict):
            expected_weights = {
                "title_alignment",
                "ai_engineering_alignment",
                "software_engineering_alignment",
                "technical_stack_alignment",
                "experience_alignment",
                "location_alignment",
                "company_alignment",
            }

            errors.extend(
                require_keys(
                    weights,
                    expected_weights,
                    "criteria.ranking.weights",
                )
            )

            for key in expected_weights:
                if key in weights:
                    errors.extend(
                        validate_score(
                            weights[key],
                            f"criteria.ranking.weights.{key}",
                        )
                    )

            numeric_weights = [
                value
                for value in weights.values()
                if isinstance(value, int)
                and not isinstance(value, bool)
            ]

            if (
                len(numeric_weights) == len(expected_weights)
                and sum(numeric_weights) != 100
            ):
                errors.append(
                    "criteria.ranking.weights must total 100; "
                    f"received {sum(numeric_weights)}."
                )
        elif weights is not None:
            errors.append(
                "criteria.ranking.weights must be an object."
            )

        penalties = ranking.get("penalties")
        if isinstance(penalties, dict):
            for key, value in penalties.items():
                errors.extend(
                    validate_score(
                        value,
                        f"criteria.ranking.penalties.{key}",
                        minimum=-100,
                        maximum=0,
                    )
                )
        elif penalties is not None:
            errors.append(
                "criteria.ranking.penalties must be an object."
            )
    elif ranking is not None:
        errors.append("criteria.ranking must be an object.")

    discovery_score = (
        ranking.get("minimum_discovery_score")
        if isinstance(ranking, dict)
        else None
    )
    analysis_score = (
        ranking.get("minimum_full_analysis_score")
        if isinstance(ranking, dict)
        else None
    )

    if (
        isinstance(discovery_score, int)
        and isinstance(analysis_score, int)
        and discovery_score > analysis_score
    ):
        errors.append(
            "criteria.ranking.minimum_discovery_score cannot exceed "
            "minimum_full_analysis_score."
        )

    return errors


def write_summary(
    criteria: dict[str, Any],
    output_path: Path,
) -> None:
    strategy = criteria["search_strategy"]
    ranking = criteria["ranking"]

    primary_rows = "\n".join(
        (
            f"- **{target['title']}** — "
            f"{target['priority_score']}/100"
        )
        for target in strategy["primary_targets"]
    )

    secondary_rows = "\n".join(
        (
            f"- **{target['title']}** — "
            f"{target['priority_score']}/100"
        )
        for target in strategy["secondary_targets"]
    )

    conditional_rows = "\n".join(
        (
            f"- **{target['title']}** — "
            f"{target['priority_score']}/100; "
            f"{'; '.join(target['conditions'])}"
        )
        for target in strategy["conditional_targets"]
    )

    excluded_rows = "\n".join(
        f"- {title}"
        for title in strategy["excluded_titles"]
    )

    content = f"""# Job Search Criteria

## Strategy

- Schema version: {criteria['schema_version']}
- Strategy version: {criteria['strategy_version']}
- Direction: {criteria['candidate']['current_direction']}

## Primary Targets

{primary_rows}

## Secondary Targets

{secondary_rows}

## Conditional Targets

{conditional_rows}

## Excluded Titles

{excluded_rows}

## Customer-Facing Preference

- Preferred level: {criteria['customer_facing_preferences']['preferred_level']}
- Customer-facing work is acceptable when it supports technical delivery, analytics, implementation, or requirements gathering.
- Customer success, support, onboarding, account growth, and pre-sales work should be deprioritized when they are the primary responsibility.

## Location

- Home region: {criteria['locations']['home_region']}
- Canada remote: {criteria['locations']['remote_rules']['canada_remote']}
- US remote: {criteria['locations']['remote_rules']['us_remote']}

## Ranking Thresholds

- Discovery threshold: {ranking['minimum_discovery_score']}/100
- Full Job Fit Analyzer threshold: {ranking['minimum_full_analysis_score']}/100

## Strategy Rule

Software engineering and AI engineering roles take priority over customer-facing, administrative, coordination, and general business analysis roles. Analytics roles remain acceptable, including roles with limited customer interaction, when they retain meaningful technical ownership.
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the Job Search Criteria contract and generate "
            "its Markdown summary."
        )
    )

    parser.add_argument(
        "criteria_path",
        nargs="?",
        type=Path,
        default=DEFAULT_CRITERIA_PATH,
        help=(
            "Path to job_search_criteria.json. "
            f"Defaults to {DEFAULT_CRITERIA_PATH}."
        ),
    )

    parser.add_argument(
        "--summary-path",
        type=Path,
        default=Path("strategy/job_search_criteria.md"),
        help=(
            "Path for the generated Markdown summary. "
            "Defaults to strategy/job_search_criteria.md."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        criteria = load_json(args.criteria_path)
        errors = validate_criteria(criteria)

        if errors:
            print("Job Search Criteria validation failed:", file=sys.stderr)

            for error in errors:
                print(f"- {error}", file=sys.stderr)

            return 1

        write_summary(criteria, args.summary_path)

        print("Job Search Criteria validation passed.")
        print(
            "Strategy version: "
            f"{criteria['strategy_version']}"
        )
        print(
            "Primary targets: "
            f"{len(criteria['search_strategy']['primary_targets'])}"
        )
        print(
            "Secondary targets: "
            f"{len(criteria['search_strategy']['secondary_targets'])}"
        )
        print(
            "Discovery threshold: "
            f"{criteria['ranking']['minimum_discovery_score']}"
        )
        print(
            "Full analysis threshold: "
            f"{criteria['ranking']['minimum_full_analysis_score']}"
        )
        print(f"Summary: {args.summary_path}")

        return 0

    except ValidationError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

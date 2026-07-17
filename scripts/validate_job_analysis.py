#!/usr/bin/env python3
"""Validate a Hermes job-fit analysis against profile evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


SCORE_FIELDS = (
    "responsibilities_match",
    "evidence_strength",
    "people_facing_alignment",
    "technology_match",
    "seniority_match",
    "logistics_match",
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        raise ValueError(f"File not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Analysis must contain a top-level JSON object.")
    return data


def load_evidence_ids(path: Path) -> set[str]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except FileNotFoundError:
        raise ValueError(f"File not found: {path}") from None
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Evidence file must contain a top-level YAML mapping.")

    items = data.get("evidence", [])
    if not isinstance(items, list):
        raise ValueError("The evidence field must be a list.")

    ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("Every evidence item must have a string id.")
        evidence_id = item["id"]
        if evidence_id in ids:
            raise ValueError(f"Duplicate evidence ID: {evidence_id}")
        ids.add(evidence_id)

    return ids


def collect_referenced_ids(analysis: dict[str, Any]) -> set[str]:
    referenced: set[str] = set()

    for item in analysis.get("requirement_map", []):
        if isinstance(item, dict):
            for evidence_id in item.get("evidence_ids", []):
                if isinstance(evidence_id, str):
                    referenced.add(evidence_id)

    for item in analysis.get("selected_evidence", []):
        if isinstance(item, dict):
            evidence_id = item.get("evidence_id")
            if isinstance(evidence_id, str):
                referenced.add(evidence_id)

    return referenced


def validate_scores(analysis: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    score = analysis.get("score")

    if not isinstance(score, dict):
        return ["score must be an object."]

    values: list[int] = []
    for field in SCORE_FIELDS:
        value = score.get(field)
        if not isinstance(value, int):
            errors.append(f"score.{field} must be an integer.")
        else:
            values.append(value)

    total = score.get("total_score")
    if not isinstance(total, int):
        errors.append("score.total_score must be an integer.")
    elif not 0 <= total <= 100:
        errors.append("score.total_score must be between 0 and 100.")

    if len(values) == len(SCORE_FIELDS) and isinstance(total, int):
        calculated = sum(values)
        if calculated != total:
            errors.append(
                f"Score components total {calculated}, but total_score is {total}."
            )

    return errors


def validate_recommendation(analysis: dict[str, Any]) -> list[str]:
    recommendation = analysis.get("recommendation")
    allowed = {"strong_apply", "apply", "selective_apply", "do_not_apply"}
    if recommendation not in allowed:
        return [f"Invalid recommendation: {recommendation!r}"]

    score = analysis.get("score", {}).get("total_score")
    hard_reject = any(
        isinstance(item, dict) and item.get("triggered") is True
        for item in analysis.get("hard_rejects", [])
    )

    if hard_reject and recommendation != "do_not_apply":
        return ["A triggered hard reject requires recommendation=do_not_apply."]

    if isinstance(score, int) and not hard_reject:
        expected = (
            "strong_apply" if score >= 80
            else "apply" if score >= 65
            else "selective_apply" if score >= 50
            else "do_not_apply"
        )
        if recommendation != expected:
            return [
                f"Score {score} normally requires recommendation={expected}, "
                f"not {recommendation}."
            ]

    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("analysis", type=Path, help="Path to analysis.json")
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("profile/evidence.yaml"),
        help="Path to evidence.yaml",
    )
    args = parser.parse_args()

    try:
        analysis = load_json(args.analysis)
        evidence_ids = load_evidence_ids(args.evidence)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors = []
    errors.extend(validate_scores(analysis))
    errors.extend(validate_recommendation(analysis))

    unknown = sorted(collect_referenced_ids(analysis) - evidence_ids)
    if unknown:
        errors.append("Unknown evidence IDs: " + ", ".join(unknown))

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Analysis validation passed.")
    print(f"Score: {analysis['score']['total_score']}/100")
    print(f"Recommendation: {analysis['recommendation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

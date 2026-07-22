#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping.")
    return data


def ids(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {
        item["id"]
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def nested_ids(groups: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(groups, dict):
        for items in groups.values():
            result.update(ids(items))
    return result


def career_ids(career: dict[str, Any]) -> set[str]:
    return ids(career.get("employment")) | ids(career.get("projects")) | ids(career.get("training_and_certifications"))


def check_many(errors, values, valid, location):
    if not isinstance(values, list):
        return
    for value in values:
        if isinstance(value, str) and value not in valid:
            errors.append(f"{location}: unknown ID {value}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("strategy", type=Path)
    parser.add_argument("--profile-dir", type=Path, default=Path("profile"))
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path.home()
        / ".hermes/skills/candidate-strategy/references/candidate-strategy-schema.json",
    )
    args = parser.parse_args()

    try:
        strategy = load_json(args.strategy)
        schema = load_json(args.schema)
        career = load_yaml(args.profile_dir / "career.yaml")
        skills = load_yaml(args.profile_dir / "skills.yaml")
        tech = load_yaml(args.profile_dir / "technologies.yaml")
        evidence = load_yaml(args.profile_dir / "evidence.yaml")
        stories = load_yaml(args.profile_dir / "interview_stories.yaml")
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors = []

    for error in Draft202012Validator(schema).iter_errors(strategy):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"schema {location}: {error.message}")

    role_ids = ids(career.get("employment"))
    project_ids = ids(career.get("projects"))
    skill_ids = nested_ids(skills.get("skills"))
    tech_ids = nested_ids(tech.get("technologies"))
    evidence_ids = ids(evidence.get("evidence"))
    story_ids = ids(stories.get("stories"))
    all_ids = career_ids(career) | skill_ids | tech_ids | evidence_ids | story_ids

    resume = strategy.get("resume_strategy", {})
    if isinstance(resume, dict):
        check_many(errors, resume.get("top_skill_ids"), skill_ids, "top_skill_ids")
        check_many(errors, resume.get("evidence_order"), evidence_ids, "evidence_order")

        for i, item in enumerate(resume.get("role_treatments", [])):
            if not isinstance(item, dict):
                continue
            role_id = item.get("role_id")
            if role_id not in role_ids:
                errors.append(f"role_treatments[{i}]: unknown role ID {role_id}")
            check_many(errors, item.get("evidence_ids"), evidence_ids, f"role_treatments[{i}]")

        for i, item in enumerate(resume.get("project_treatments", [])):
            if not isinstance(item, dict):
                continue
            project_id = item.get("project_id")
            if project_id not in project_ids:
                errors.append(f"project_treatments[{i}]: unknown project ID {project_id}")
            check_many(errors, item.get("evidence_ids"), evidence_ids, f"project_treatments[{i}]")

    cover = strategy.get("cover_letter_strategy", {})
    if isinstance(cover, dict):
        check_many(errors, cover.get("evidence_ids"), evidence_ids, "cover_letter_strategy")

    interview = strategy.get("interview_strategy", {})
    if isinstance(interview, dict):
        for i, item in enumerate(interview.get("selected_stories", [])):
            if isinstance(item, dict) and item.get("story_id") not in story_ids:
                errors.append(f"selected_stories[{i}]: unknown story ID {item.get('story_id')}")

    keyword_strategy = strategy.get("keyword_strategy", {})
    if isinstance(keyword_strategy, dict):
        for group, items_list in keyword_strategy.items():
            if isinstance(items_list, list):
                for i, item in enumerate(items_list):
                    if isinstance(item, dict):
                        check_many(
                            errors,
                            item.get("supporting_ids"),
                            all_ids,
                            f"keyword_strategy.{group}[{i}]",
                        )

    for i, item in enumerate(strategy.get("application_answer_strategy", [])):
        if isinstance(item, dict):
            check_many(errors, item.get("recommended_ids"), all_ids, f"application_answer_strategy[{i}]")

    handoffs = strategy.get("downstream_handoffs", {})
    if isinstance(handoffs, dict):
        for name, handoff in handoffs.items():
            if isinstance(handoff, dict):
                check_many(errors, handoff.get("ids"), all_ids, f"downstream_handoffs.{name}")

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Candidate strategy validation passed.")
    print(f"Preserved score: {strategy['source_analysis']['total_score']}/100")
    print(f"Preserved recommendation: {strategy['source_analysis']['recommendation']}")
    print(f"Strategy: {strategy['strategy_headline']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

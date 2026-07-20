#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from filter_job_leads import LOWER_MAINLAND_CITIES
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


@dataclass(frozen=True)
class ScoreResult:
    preliminary_score: int
    components: dict[str, int]
    penalties: tuple[dict[str, Any], ...]
    full_analysis_recommended: bool


def normalized_text(value: str) -> str:
    value = value.casefold().replace("-", " ")
    value = re.sub(r"[^\w+#. ]", " ", value)
    return " ".join(value.split())


def lead_text(lead: dict[str, Any]) -> str:
    content = lead["content"]
    values = [
        lead["position"]["title"],
        content["description_text"],
        content.get("summary") or "",
        *content.get("responsibilities", []),
        *content.get("qualifications", []),
        *lead["requirements"].get("technical_skills", []),
        *lead["requirements"].get("domain_skills", []),
    ]
    return normalized_text(" ".join(values))


def title_similarity(first: str, second: str) -> float:
    first_normalized = normalized_text(first)
    second_normalized = normalized_text(second)

    if first_normalized == second_normalized:
        return 1.0

    if (
        first_normalized in second_normalized
        or second_normalized in first_normalized
    ):
        shorter = min(len(first_normalized), len(second_normalized))
        longer = max(len(first_normalized), len(second_normalized))
        return max(0.88, shorter / longer)

    return SequenceMatcher(
        None,
        first_normalized,
        second_normalized,
    ).ratio()


def score_title_alignment(
    lead: dict[str, Any],
    criteria: dict[str, Any],
) -> int:
    title = lead["position"]["title"]
    strategy = criteria["search_strategy"]
    targets = (
        strategy["primary_targets"]
        + strategy["secondary_targets"]
        + strategy["conditional_targets"]
    )

    best_score = 25

    for target in targets:
        similarity = title_similarity(title, target["title"])
        if similarity < 0.60:
            continue

        adjusted = round(target["priority_score"] * similarity)
        best_score = max(best_score, adjusted)

    return min(100, best_score)


def score_ai_alignment(lead: dict[str, Any]) -> int:
    function_scores = {
        "ai_engineering": 100,
        "machine_learning": 82,
        "software_engineering": 48,
        "product": 45,
        "solutions_engineering": 45,
        "data_engineering": 38,
        "analytics_engineering": 28,
        "implementation": 25,
        "data_analytics": 20,
        "business_analysis": 12,
    }
    score = function_scores.get(
        lead["position"]["primary_function"],
        5,
    )
    text = lead_text(lead)

    strong_signals = (
        "ai agents",
        "ai agent",
        "llm application development",
        "large language model",
        "generative ai",
        "genai",
        "agentic",
    )
    moderate_signals = (
        "machine learning",
        "ai enabled product development",
        "ai powered",
        "artificial intelligence",
    )

    if any(signal in text for signal in strong_signals):
        score = max(score, 92)
    elif any(signal in text for signal in moderate_signals):
        score = max(score, 72)

    return min(100, score)


def score_software_alignment(lead: dict[str, Any]) -> int:
    function_scores = {
        "software_engineering": 100,
        "ai_engineering": 96,
        "product": 88,
        "machine_learning": 85,
        "data_engineering": 82,
        "analytics_engineering": 72,
        "solutions_engineering": 68,
        "implementation": 62,
        "data_analytics": 48,
        "business_analysis": 38,
        "support": 30,
    }
    score = function_scores.get(
        lead["position"]["primary_function"],
        20,
    )
    text = lead_text(lead)
    engineering_signals = (
        "software development",
        "write code",
        "build apis",
        "backend",
        "full stack",
        "production systems",
        "application development",
    )

    if any(signal in text for signal in engineering_signals):
        score = max(score, 82)

    return min(100, score)


TECHNICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "AI agents": ("ai agent", "agentic", "multi agent"),
    "LLM application development": (
        "llm",
        "large language model",
        "generative ai",
        "genai",
    ),
    "Python": ("python",),
    "API development and integration": (
        "rest api",
        "api development",
        "api integration",
        "apis",
    ),
    "Workflow automation": ("workflow automation", "process automation"),
    "Backend systems": ("backend", "server side"),
    "AI-enabled product development": (
        "ai enabled product",
        "ai powered",
        "ai product",
    ),
    "Structured outputs and validation": (
        "structured output",
        "schema validation",
        "json schema",
    ),
    "Docker": ("docker", "containerization", "containerisation"),
    "SQL": ("sql", "postgresql", "postgres", "mysql"),
    "Data pipelines": ("data pipeline", "etl", "elt"),
    "Cloud platforms": ("aws", "azure", "google cloud", "gcp"),
    "Full-stack development": ("full stack", "fullstack"),
    "Analytics engineering": ("analytics engineering", "dbt"),
    "Browser automation": ("browser automation", "playwright", "selenium"),
    "DevOps and deployment": (
        "devops",
        "continuous integration",
        "continuous deployment",
        "ci/cd",
        "deployment",
    ),
    "Pure visual design": ("visual design", "graphic design"),
    "CMS-only development": ("cms", "wordpress"),
    "Manual reporting without engineering ownership": (
        "manual reporting",
        "spreadsheet reporting",
    ),
    "Pure frontend styling work": ("frontend styling", "css styling"),
}


def score_technical_stack(
    lead: dict[str, Any],
    criteria: dict[str, Any],
) -> int:
    text = lead_text(lead)
    technical_focus = criteria["technical_focus"]
    matches: list[int] = []

    for group in ("high_priority", "medium_priority", "low_priority"):
        for preference in technical_focus[group]:
            aliases = TECHNICAL_ALIASES.get(
                preference["name"],
                (normalized_text(preference["name"]),),
            )
            if any(normalized_text(alias) in text for alias in aliases):
                matches.append(preference["score"])

    if not matches:
        return 35

    strongest = sorted(matches, reverse=True)[:3]
    return round(sum(strongest) / len(strongest))


def score_experience_alignment(lead: dict[str, Any]) -> int:
    years = lead["requirements"].get("years_experience_min")
    seniority = lead["position"]["seniority"]

    if years is None:
        base = 78
    elif years <= 3:
        base = 96
    elif years <= 5:
        base = 84
    elif years <= 7:
        base = 68
    elif years <= 10:
        base = 48
    else:
        base = 25

    seniority_adjustments = {
        "intern": -25,
        "entry": -5,
        "junior": 0,
        "intermediate": 8,
        "senior": -5,
        "lead": -12,
        "manager": -20,
        "director": -35,
        "executive": -50,
    }

    return max(0, min(100, base + seniority_adjustments.get(seniority, 0)))


def score_location_alignment(lead: dict[str, Any]) -> int:
    location = lead["location"]
    can_hire = location.get("can_hire_in_canada")
    workplace = location["workplace_type"]
    city = normalized_text(location.get("city") or "")
    region = normalized_text(location.get("region") or "")

    if can_hire is False:
        return 0

    if workplace == "remote":
        return 100 if can_hire is True else 65

    in_lower_mainland = city in LOWER_MAINLAND_CITIES
    if workplace == "hybrid":
        if in_lower_mainland:
            return 95
        if region == "british columbia" and not city:
            return 65
        return 25

    if workplace == "on_site":
        if in_lower_mainland:
            return 88
        if region == "british columbia" and not city:
            return 55
        return 10

    if in_lower_mainland:
        return 85

    return 60 if can_hire is True else 50


COMPANY_ALIASES: dict[str, tuple[str, ...]] = {
    "AI product companies": ("ai product", "ai platform", "artificial intelligence"),
    "Developer tools": ("developer tool", "developer platform"),
    "B2B SaaS": ("b2b saas", "saas platform", "software as a service"),
    "Workflow automation": ("workflow automation", "process automation"),
    "Data and analytics platforms": ("analytics platform", "data platform"),
    "Productivity software": ("productivity software", "productivity platform"),
    "Applied AI startups": ("applied ai", "ai startup"),
    "Enterprise software": ("enterprise software", "enterprise platform"),
    "Cleantech": ("cleantech", "clean technology"),
    "Fintech": ("fintech", "financial technology"),
    "Insurtech": ("insurtech", "insurance technology"),
    "Public sector technology": ("public sector technology", "government technology"),
    "General consulting": ("consulting firm", "consultancy"),
    "Digital agencies": ("digital agency",),
    "Non-technical service companies": ("service company",),
}


def score_company_alignment(
    lead: dict[str, Any],
    criteria: dict[str, Any],
) -> int:
    text = lead_text(lead)
    preferences = criteria["company_preferences"]
    matches: list[int] = []

    for group in ("preferred", "acceptable", "lower_priority"):
        for preference in preferences[group]:
            aliases = COMPANY_ALIASES.get(
                preference["name"],
                (normalized_text(preference["name"]),),
            )
            if any(normalized_text(alias) in text for alias in aliases):
                matches.append(preference["score"])

    return max(matches) if matches else 65


def applied_penalties(
    lead: dict[str, Any],
    criteria: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    configured = criteria["ranking"]["penalties"]
    function = lead["position"]["primary_function"]
    customer_level = lead["requirements"]["customer_facing_level"]
    penalties: list[dict[str, Any]] = []

    def add(name: str, reason: str) -> None:
        penalties.append(
            {
                "name": name,
                "value": configured[name],
                "reason": reason,
            }
        )

    if customer_level == "primary_responsibility":
        add(
            "primarily_customer_facing",
            "Customer-facing work is the primary responsibility.",
        )
    if function == "sales":
        add("primarily_sales", "The role's primary function is sales.")
    if function == "support":
        add("primarily_support", "The role's primary function is support.")
    if function == "administration":
        add(
            "primarily_administrative",
            "The role's primary function is administration.",
        )

    return tuple(penalties)


def calculate_score(
    lead: dict[str, Any],
    criteria: dict[str, Any],
) -> ScoreResult:
    if lead["discovery"]["hard_filter_result"] not in {
        "pass",
        "manual_review",
    }:
        raise JobLeadValidationError(
            "A lead must pass hard filtering or be marked for manual review "
            "before preliminary scoring."
        )

    components = {
        "title_alignment": score_title_alignment(lead, criteria),
        "ai_engineering_alignment": score_ai_alignment(lead),
        "software_engineering_alignment": score_software_alignment(lead),
        "technical_stack_alignment": score_technical_stack(lead, criteria),
        "experience_alignment": score_experience_alignment(lead),
        "location_alignment": score_location_alignment(lead),
        "company_alignment": score_company_alignment(lead, criteria),
    }
    weights = criteria["ranking"]["weights"]
    weighted_score = sum(
        components[name] * weight / 100
        for name, weight in weights.items()
    )
    penalties = applied_penalties(lead, criteria)
    preliminary_score = round(
        max(0, min(100, weighted_score + sum(p["value"] for p in penalties)))
    )
    full_analysis_recommended = (
        lead["discovery"]["hard_filter_result"] == "pass"
        and preliminary_score
        >= criteria["ranking"]["minimum_full_analysis_score"]
    )

    return ScoreResult(
        preliminary_score=preliminary_score,
        components=components,
        penalties=penalties,
        full_analysis_recommended=full_analysis_recommended,
    )


def apply_score_result(
    lead: dict[str, Any],
    result: ScoreResult,
    criteria: dict[str, Any],
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
    discovery = lead["discovery"]
    discovery["preliminary_score"] = result.preliminary_score
    discovery["score_components"] = result.components
    discovery["penalties"] = list(result.penalties)
    discovery["full_analysis_recommended"] = result.full_analysis_recommended

    if discovery["hard_filter_result"] == "manual_review":
        lead["status"]["lead_status"] = "new"
    elif (
        result.preliminary_score
        >= criteria["ranking"]["minimum_discovery_score"]
    ):
        lead["status"]["lead_status"] = "eligible"
    else:
        lead["status"]["lead_status"] = "rejected"

    if existing_status in protected_statuses:
        lead["status"]["lead_status"] = existing_status


def load_lead_files(directory: Path) -> list[tuple[Path, dict[str, Any]]]:
    if not directory.exists():
        raise JobLeadValidationError(f"Leads directory does not exist: {directory}")
    return [(path, load_json(path)) for path in sorted(directory.glob("*.json"))]


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def score_leads(
    leads: list[tuple[Path, dict[str, Any]]],
    criteria: dict[str, Any],
    dry_run: bool = False,
) -> list[tuple[str, ScoreResult]]:
    results: list[tuple[str, ScoreResult]] = []

    for path, lead in leads:
        if lead["status"]["lead_status"] == "archived":
            continue
        if lead["discovery"]["hard_filter_result"] == "fail":
            continue

        result = calculate_score(lead, criteria)
        results.append((lead["lead_id"], result))

        if not dry_run:
            apply_score_result(lead, result, criteria)
            write_json(path, lead)

    return sorted(
        results,
        key=lambda item: (-item[1].preliminary_score, item[0]),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score and rank hard-filtered Job Leads."
    )
    parser.add_argument("--leads-directory", type=Path, default=DEFAULT_LEADS_DIRECTORY)
    parser.add_argument("--criteria", type=Path, default=DEFAULT_CRITERIA_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
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

        for path, lead in leads:
            errors = validate_schema(lead, schema)
            errors.extend(validate_business_rules(lead))
            if errors:
                print(f"Scoring stopped: invalid Job Lead {path}", file=sys.stderr)
                for error in errors:
                    print(f"- {error}", file=sys.stderr)
                return 1

        results = score_leads(leads, criteria, args.dry_run)

        if not args.dry_run:
            for path, lead in load_lead_files(args.leads_directory):
                errors = validate_schema(lead, schema)
                errors.extend(validate_business_rules(lead))
                if errors:
                    print(f"Scoring produced an invalid Job Lead: {path}", file=sys.stderr)
                    for error in errors:
                        print(f"- {error}", file=sys.stderr)
                    return 1

        print(f"Ranked {len(results)} Job Lead(s).")
        for rank, (lead_id, result) in enumerate(results, start=1):
            recommendation = (
                "full analysis"
                if result.full_analysis_recommended
                else "discovery only"
            )
            print(
                f"{rank}. {lead_id}: {result.preliminary_score}/100 "
                f"({recommendation})"
            )
        if args.dry_run:
            print("Dry run: no Job Lead files were modified.")
        return 0
    except JobLeadValidationError as exc:
        print(f"Scoring failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

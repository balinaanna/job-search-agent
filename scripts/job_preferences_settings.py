from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

WEIGHT_KEYS = (
    "responsibilities_match", "evidence_strength", "people_facing_alignment",
    "technology_match", "seniority_match", "logistics_match",
)


def _read(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a mapping.")
    return value


def load_job_preferences(path: Path) -> dict[str, Any]:
    data = _read(path)
    work = data.get("work_arrangement", {}) or {}
    travel = work.get("travel", {}) or {}
    driving = work.get("driving", {}) or {}
    employment = data.get("employment", {}) or {}
    fit = data.get("fit_scoring", {}) or {}
    strategy = data.get("application_strategy", {}) or {}
    objective = data.get("objective", {}) or {}
    target = data.get("target_role_families", {}) or {}
    return {
        "objective": {
            "primary": objective.get("primary", ""),
            "secondary": objective.get("secondary", ""),
        },
        "target_role_families": {
            "priority_1": target.get("priority_1", []),
            "priority_2": target.get("priority_2", []),
        },
        "preferred_work_characteristics": data.get("preferred_work_characteristics", []),
        "work_arrangement": {
            "preferred": work.get("preferred", []),
            "location_base": str(work.get("location_base", "")).strip(),
            "travel_acceptable": str(travel.get("acceptable", "")).strip(),
            "travel_avoid": str(travel.get("avoid", "")).strip(),
            "has_licence": bool(driving.get("has_licence", False)),
            "regular_car_access": bool(driving.get("regular_car_access", False)),
            "driving_rule": str(driving.get("rule", "")).strip(),
        },
        "employment": {
            "types_preferred": employment.get("types_preferred", []),
            "sponsorship_required": bool(employment.get("sponsorship_required", False)),
        },
        "fit_scoring": {
            "weights": {key: fit.get("weights", {}).get(key, 0) for key in WEIGHT_KEYS},
            "hard_reject_conditions": fit.get("hard_reject_conditions", []),
        },
        "application_strategy": {
            "apply_when": strategy.get("apply_when", []),
            "do_not_apply_when": strategy.get("do_not_apply_when", []),
            "human_approval_required_before": strategy.get("human_approval_required_before", []),
        },
    }


def _strings(value: Any, name: str, *, minimum: int = 1, maximum: int = 40) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list.")
    cleaned = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if len(cleaned) < minimum:
        raise ValueError(f"{name} needs at least {minimum} item(s).")
    if len(cleaned) > maximum:
        raise ValueError(f"{name} cannot exceed {maximum} items.")
    if len({item.casefold() for item in cleaned}) != len(cleaned):
        raise ValueError(f"{name} cannot contain duplicates.")
    return cleaned


def _text(value: Any, name: str, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text.")
    cleaned = value.strip()
    if required and not cleaned:
        raise ValueError(f"{name} is required.")
    return cleaned


def save_job_preferences(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be an object.")

    objective = payload.get("objective", {}) or {}
    primary_objective = _text(objective.get("primary"), "Primary objective", required=True)
    secondary_objective = _text(objective.get("secondary"), "Secondary objective")

    target = payload.get("target_role_families", {}) or {}
    priority_1 = _strings(target.get("priority_1"), "Priority 1 target roles", maximum=30)
    priority_2 = _strings(target.get("priority_2"), "Priority 2 target roles", minimum=0, maximum=30)
    characteristics = _strings(payload.get("preferred_work_characteristics"), "Preferred work characteristics", maximum=20)

    work = payload.get("work_arrangement", {}) or {}
    preferred_arrangement = _strings(work.get("preferred"), "Preferred work arrangement", maximum=10)
    location_base = _text(work.get("location_base"), "Location base", required=True)
    travel_acceptable = _text(work.get("travel_acceptable"), "Acceptable travel")
    travel_avoid = _text(work.get("travel_avoid"), "Travel to avoid")
    has_licence = bool(work.get("has_licence"))
    regular_car_access = bool(work.get("regular_car_access"))
    driving_rule = _text(work.get("driving_rule"), "Driving rule")

    employment = payload.get("employment", {}) or {}
    types_preferred = _strings(employment.get("types_preferred"), "Preferred employment types", maximum=10)
    sponsorship_required = bool(employment.get("sponsorship_required"))

    fit = payload.get("fit_scoring", {}) or {}
    weights = fit.get("weights")
    if not isinstance(weights, dict):
        raise ValueError("Fit-scoring weights must be an object.")
    cleaned_weights: dict[str, int] = {}
    for key in WEIGHT_KEYS:
        value = weights.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"Weight '{key}' must be a non-negative whole number.")
        cleaned_weights[key] = value
    if sum(cleaned_weights.values()) != 100:
        raise ValueError("Fit-scoring weights must add up to exactly 100.")
    hard_reject_conditions = _strings(fit.get("hard_reject_conditions"), "Hard-reject conditions", minimum=0, maximum=20)

    strategy = payload.get("application_strategy", {}) or {}
    apply_when = _strings(strategy.get("apply_when"), "Apply-when conditions", minimum=0, maximum=15)
    do_not_apply_when = _strings(strategy.get("do_not_apply_when"), "Do-not-apply conditions", minimum=0, maximum=15)
    human_approval_required_before = _strings(
        strategy.get("human_approval_required_before"), "Human-approval checkpoints", maximum=20
    )

    data = _read(path)
    data["last_reviewed"] = date.today().isoformat()
    data["objective"] = {"primary": primary_objective, "secondary": secondary_objective}
    data["target_role_families"] = {"priority_1": priority_1, "priority_2": priority_2}
    data["preferred_work_characteristics"] = characteristics
    work_arrangement = data.setdefault("work_arrangement", {})
    work_arrangement["preferred"] = preferred_arrangement
    work_arrangement["location_base"] = location_base
    work_arrangement["travel"] = {"acceptable": travel_acceptable, "avoid": travel_avoid}
    work_arrangement["driving"] = {
        "has_licence": has_licence, "regular_car_access": regular_car_access, "rule": driving_rule,
    }
    data["employment"] = {"types_preferred": types_preferred, "sponsorship_required": sponsorship_required}
    fit_scoring = data.setdefault("fit_scoring", {})
    fit_scoring["weights"] = cleaned_weights
    fit_scoring["hard_reject_conditions"] = hard_reject_conditions
    data["application_strategy"] = {
        "apply_when": apply_when,
        "do_not_apply_when": do_not_apply_when,
        "human_approval_required_before": human_approval_required_before,
    }

    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    return load_job_preferences(path)

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FREQUENCIES = {"manual", "daily", "weekly"}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object.")
    return value


def load_search_settings(criteria_path: Path, sources_path: Path, schedule_path: Path) -> dict[str, Any]:
    criteria = _read(criteria_path)
    source_config = _read(sources_path)
    schedule = _read(schedule_path) if schedule_path.exists() else {"frequency": "manual"}
    return {
        "roles": [item["title"] for item in criteria["search_strategy"]["primary_targets"]],
        "locations": criteria["locations"]["preferred"],
        "frequency": schedule.get("frequency", "manual"),
        "sources": [
            {
                "id": f"{item['platform']}:{item.get('board_token') or item.get('site')}",
                "company": item["company"],
                "platform": item["platform"],
                "enabled": item.get("enabled", True),
            }
            for item in source_config["sources"]
        ],
    }


def _strings(value: Any, name: str, maximum: int) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list.")
    cleaned = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if not cleaned or len(cleaned) > maximum:
        raise ValueError(f"Choose between 1 and {maximum} {name.lower()}.")
    if len({item.casefold() for item in cleaned}) != len(cleaned):
        raise ValueError(f"{name} cannot contain duplicates.")
    return cleaned


def save_search_settings(payload: dict[str, Any], criteria_path: Path, sources_path: Path, schedule_path: Path) -> dict[str, Any]:
    roles = _strings(payload.get("roles"), "Roles", 20)
    locations = _strings(payload.get("locations"), "Locations", 15)
    frequency = payload.get("frequency")
    if frequency not in FREQUENCIES:
        raise ValueError("Frequency must be manual, daily, or weekly.")
    enabled_source_ids = payload.get("enabled_source_ids")
    if not isinstance(enabled_source_ids, list) or not all(isinstance(item, str) for item in enabled_source_ids):
        raise ValueError("Enabled sources must be a list.")

    criteria = _read(criteria_path)
    existing = {item["title"].casefold(): item for item in criteria["search_strategy"]["primary_targets"]}
    criteria["search_strategy"]["primary_targets"] = [
        existing.get(title.casefold(), {
            "title": title,
            "priority_score": max(81, 100 - index),
            "reasons": ["Selected as a primary target in Search Settings."],
        })
        for index, title in enumerate(roles)
    ]
    criteria["locations"]["preferred"] = locations
    criteria["strategy_version"] = int(criteria.get("strategy_version", 0)) + 1

    source_config = _read(sources_path)
    known_ids = {f"{item['platform']}:{item.get('board_token') or item.get('site')}" for item in source_config["sources"]}
    unknown = set(enabled_source_ids) - known_ids
    if unknown:
        raise ValueError("An unknown job source was selected.")
    for item in source_config["sources"]:
        source_id = f"{item['platform']}:{item.get('board_token') or item.get('site')}"
        item["enabled"] = source_id in enabled_source_ids
    if not enabled_source_ids:
        raise ValueError("Enable at least one job source.")

    criteria_path.write_text(json.dumps(criteria, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    sources_path.write_text(json.dumps(source_config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    schedule_path.write_text(json.dumps({"frequency": frequency}, indent=2) + "\n", encoding="utf-8")
    return load_search_settings(criteria_path, sources_path, schedule_path)

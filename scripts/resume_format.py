from __future__ import annotations

import re


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def format_date(value: object) -> str:
    raw = str(value or "").strip()
    match = re.match(r"^(\d{4})-(\d{2})$", raw)
    if match:
        year, month = match.groups()
        if 1 <= int(month) <= 12:
            return f"{MONTHS[int(month) - 1]} {year}"
    return raw


def date_range(dates: dict) -> str:
    return " - ".join(part for part in (format_date(dates.get("start")), format_date(dates.get("end"))) if part)


def training_date(item: dict) -> str:
    if item.get("dates"):
        return date_range(item["dates"])
    return format_date(item.get("completion"))


def training_suffix(item: dict) -> str:
    provider_location = ", ".join(part for part in (str(item.get("provider") or ""), str(item.get("location") or "")) if part)
    suffix = f" - {provider_location}" if provider_location else ""
    date_display = training_date(item)
    if date_display:
        suffix += f" ({date_display})"
    return suffix


def humanize_group(name: str) -> str:
    return " ".join(word.upper() if word.lower() == "ai" else word.title() for word in name.replace("_", " ").split(" "))


def recency_key(item: dict) -> str:
    dates = item.get("dates")
    if isinstance(dates, dict):
        return str(dates.get("end") or dates.get("start") or "")
    return str(item.get("completion") or "")


def sort_recent_first(items: list) -> list:
    return sorted(items, key=recency_key, reverse=True)


GROUP_ALIASES = {
    "ai_and_automation": "ai",
}


def merge_skill_groups(skills: dict, technologies: dict) -> list:
    """Combine skills and technologies into one ordered list of (group, items),
    folding aliased groups (e.g. ai_and_automation into ai) into a single heading,
    dropping later duplicate names (case-insensitive), and dropping empty groups."""
    seen_names: set[str] = set()
    order: list[str] = []
    grouped: dict[str, list] = {}
    for group, items in list(skills.items()) + list(technologies.items()):
        canonical = GROUP_ALIASES.get(group, group)
        deduped = []
        for item in items:
            name_key = str(item.get("name", "")).strip().lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)
            deduped.append(item)
        if not deduped:
            continue
        if canonical not in grouped:
            grouped[canonical] = []
            order.append(canonical)
        grouped[canonical].extend(deduped)
    return [(name, grouped[name]) for name in order]

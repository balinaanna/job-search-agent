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

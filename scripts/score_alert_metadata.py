from __future__ import annotations

from typing import Any

from filter_job_leads import contains_phrase
from score_job_leads import title_similarity


def score_alert_metadata(job: dict[str, Any], criteria: dict[str, Any]) -> dict[str, Any]:
    """Estimate fit from locally stored alert metadata without opening the job board."""
    title = str(job.get("title") or "").strip()
    strategy = criteria["search_strategy"]
    if any(contains_phrase(title, excluded) for excluded in strategy["excluded_titles"]):
        return {
            "score": 5,
            "label": "Low title match",
            "basis": "Title only",
            "limitations": ["The title is explicitly excluded by the search strategy.", "Requirements, location, and seniority are not yet verified."],
        }
    targets = strategy["primary_targets"] + strategy["secondary_targets"] + strategy["conditional_targets"]
    best = max((target["priority_score"] * title_similarity(title, target["title"]) for target in targets), default=25)
    title_score = max(20, min(100, round(best)))
    # Unknown requirements, logistics, and employer context stay neutral rather than receiving assumed credit.
    score = round(title_score * 0.75 + 50 * 0.25)
    location = str(job.get("location") or "").casefold()
    if location and any(value in location for value in ("remote", "canada", "british columbia", "vancouver", "richmond", "burnaby")):
        score += 4
    elif location and any(value in location for value in ("united states", " usa", "new york", "california", "europe", "uk only")):
        score -= 15
    score = max(0, min(100, score))
    label = "Promising alert match" if score >= 75 else "Possible alert match" if score >= 55 else "Weak alert match"
    return {
        "score": score,
        "label": label,
        "basis": "Alert metadata",
        "limitations": ["Calculated without opening the job board.", "Requirements, seniority, and responsibilities are not yet verified."],
    }

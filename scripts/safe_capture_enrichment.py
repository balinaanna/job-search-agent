from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from collect_job_postings import CollectionError, fetch_json, greenhouse_postings, lever_postings, load_sources, write_postings
from safe_capture_policy import automatic_capture_plan


def configured_source(plan: dict[str, str], sources_path: Path) -> dict[str, Any]:
    for source in load_sources(sources_path):
        account = source.get("board_token") if plan["platform"] == "greenhouse" else source.get("site")
        if source["platform"] == plan["platform"] and account == plan["account"]:
            return source
    raise CollectionError(
        f"{plan['platform'].title()} account '{plan['account']}' has not been reviewed and configured."
    )


def enrich_alert_posting(
    job: dict[str, Any],
    sources_path: Path,
    output_directory: Path,
    collected_at: str,
    fetcher: Callable[[str], Any] = fetch_json,
) -> dict[str, Any]:
    plan = automatic_capture_plan(job["posting_url"])
    if not plan:
        raise CollectionError("This posting requires manual capture under safe capture mode.")
    source = configured_source(plan, sources_path)
    payload = fetcher(plan["api_url"])
    postings = (
        greenhouse_postings(source, {"jobs": [payload]}, collected_at)
        if plan["platform"] == "greenhouse"
        else lever_postings(source, [payload], collected_at)
    )
    if len(postings) != 1 or len(postings[0].get("description_text", "")) < 200:
        raise CollectionError("The approved ATS did not return a complete job description.")
    write_postings(postings, output_directory)
    return postings[0]

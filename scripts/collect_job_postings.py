#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_SOURCES_PATH = Path("strategy/job_sources.json")
DEFAULT_OUTPUT_DIRECTORY = Path("data/raw-job-postings")
USER_AGENT = "job-search-agent/1.0 (+local personal job discovery)"


class CollectionError(Exception):
    """Raised when a configured public job source cannot be collected safely."""


class PlainTextHTMLParser(HTMLParser):
    BLOCK_TAGS = {
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "li",
        "p",
        "section",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(value: str) -> str:
    parser = PlainTextHTMLParser()
    parser.feed(unescape(value))
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line)


def fetch_json(url: str, timeout: float = 30.0) -> Any:
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        raise CollectionError(
            f"HTTP {exc.code} while collecting {url}"
        ) from exc
    except URLError as exc:
        raise CollectionError(f"Unable to collect {url}: {exc.reason}") from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise CollectionError(f"Source returned invalid JSON: {url}") from exc


def required_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CollectionError(f"{path} must be a non-empty string.")
    return value.strip()


def optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def optional_date(value: Any) -> str | None:
    text = optional_string(value)
    if not text:
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", text)
    return match.group(1) if match else None


def salary_period(value: Any) -> str | None:
    text = optional_string(value)
    if not text:
        return None
    normalized = text.casefold().replace("_", "-")
    aliases = {
        "annual": "year",
        "annually": "year",
        "yearly": "year",
        "per-year": "year",
        "per-year-salary": "year",
        "monthly": "month",
        "per-month": "month",
        "weekly": "week",
        "per-week": "week",
        "daily": "day",
        "per-day": "day",
        "hourly": "hour",
        "per-hour": "hour",
    }
    if normalized in {"year", "month", "week", "day", "hour"}:
        return normalized
    return aliases.get(normalized)


def lever_description(job: dict[str, Any]) -> str | None:
    direct = optional_string(job.get("descriptionPlain"))
    if direct:
        return direct

    parts = [
        optional_string(job.get("openingPlain")),
        optional_string(job.get("descriptionBodyPlain")),
        optional_string(job.get("additionalPlain")),
    ]
    lists = job.get("lists")
    if isinstance(lists, list):
        for item in lists:
            if not isinstance(item, dict):
                continue
            heading = optional_string(item.get("text"))
            content = optional_string(item.get("content"))
            if heading:
                parts.append(heading)
            if content:
                parts.append(html_to_text(content))

    combined = "\n".join(part for part in parts if part)
    if combined:
        return combined

    html_description = optional_string(job.get("description"))
    if html_description:
        return html_to_text(html_description) or None
    return None


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "job"


def greenhouse_url(board_token: str) -> str:
    token = quote(board_token, safe="")
    return (
        "https://boards-api.greenhouse.io/v1/boards/"
        f"{token}/jobs?content=true"
    )


def lever_url(site: str, region: str) -> str:
    host = "api.eu.lever.co" if region == "eu" else "api.lever.co"
    return f"https://{host}/v0/postings/{quote(site, safe='')}?mode=json"


def greenhouse_postings(
    source: dict[str, Any],
    payload: Any,
    collected_at: str,
) -> list[dict[str, Any]]:
    company = required_string(source.get("company"), "source.company")
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise CollectionError("Greenhouse response must contain a jobs array.")

    postings: list[dict[str, Any]] = []
    for index, job in enumerate(payload["jobs"]):
        if not isinstance(job, dict):
            raise CollectionError(f"Greenhouse jobs[{index}] must be an object.")
        job_id = job.get("id")
        title = required_string(job.get("title"), f"jobs[{index}].title")
        posting_url = required_string(
            job.get("absolute_url"), f"jobs[{index}].absolute_url"
        )
        content = html_to_text(required_string(
            job.get("content"), f"jobs[{index}].content"
        ))
        location = job.get("location")
        location_name = (
            optional_string(location.get("name"))
            if isinstance(location, dict)
            else None
        )
        departments = job.get("departments")
        department = None
        if isinstance(departments, list):
            department = next(
                (
                    optional_string(item.get("name"))
                    for item in departments
                    if isinstance(item, dict) and item.get("name")
                ),
                None,
            )

        postings.append(
            {
                "company": company,
                "role": title,
                "posting_url": posting_url,
                "application_url": posting_url,
                "external_job_id": str(job_id) if job_id is not None else None,
                "platform": "greenhouse",
                "description_text": content,
                "location_raw": location_name,
                "workplace_type_raw": None,
                "employment_type_raw": None,
                "department": department,
                "salary": {
                    "minimum": None,
                    "maximum": None,
                    "currency": None,
                    "period": None,
                    "source": None,
                },
                "posted_date": optional_date(job.get("first_published")),
                "deadline": optional_date(job.get("application_deadline")),
                "collected_at": collected_at,
                "search_query": f"{company} Greenhouse careers",
            }
        )
    return postings


def lever_postings(
    source: dict[str, Any],
    payload: Any,
    collected_at: str,
) -> list[dict[str, Any]]:
    company = required_string(source.get("company"), "source.company")
    if not isinstance(payload, list):
        raise CollectionError("Lever response must be an array.")

    postings: list[dict[str, Any]] = []
    for index, job in enumerate(payload):
        if not isinstance(job, dict):
            raise CollectionError(f"Lever postings[{index}] must be an object.")
        categories = job.get("categories")
        if not isinstance(categories, dict):
            categories = {}
        salary_range = job.get("salaryRange")
        if not isinstance(salary_range, dict):
            salary_range = {}

        description = lever_description(job)
        if not description:
            continue

        postings.append(
            {
                "company": company,
                "role": required_string(job.get("text"), f"postings[{index}].text"),
                "posting_url": required_string(
                    job.get("hostedUrl"), f"postings[{index}].hostedUrl"
                ),
                "application_url": optional_string(job.get("applyUrl")),
                "external_job_id": optional_string(job.get("id")),
                "platform": "lever",
                "description_text": description,
                "location_raw": optional_string(categories.get("location")),
                "workplace_type_raw": optional_string(job.get("workplaceType")),
                "employment_type_raw": optional_string(categories.get("commitment")),
                "department": optional_string(
                    categories.get("department") or categories.get("team")
                ),
                "salary": {
                    "minimum": salary_range.get("min"),
                    "maximum": salary_range.get("max"),
                    "currency": optional_string(salary_range.get("currency")),
                    "period": salary_period(salary_range.get("interval")),
                    "source": "employer" if salary_range else None,
                },
                "posted_date": None,
                "deadline": None,
                "collected_at": collected_at,
                "search_query": f"{company} Lever careers",
            }
        )
    return postings


def validate_source(source: Any, index: int) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise CollectionError(f"sources[{index}] must be an object.")
    required_string(source.get("company"), f"sources[{index}].company")
    platform = required_string(source.get("platform"), f"sources[{index}].platform")
    if platform == "greenhouse":
        required_string(source.get("board_token"), f"sources[{index}].board_token")
    elif platform == "lever":
        required_string(source.get("site"), f"sources[{index}].site")
        region = source.get("region", "global")
        if region not in {"global", "eu"}:
            raise CollectionError(
                f"sources[{index}].region must be global or eu."
            )
    else:
        raise CollectionError(
            f"sources[{index}].platform must be greenhouse or lever."
        )
    return source


def collect_source(
    source: dict[str, Any],
    collected_at: str,
    fetcher: Callable[[str], Any] = fetch_json,
) -> list[dict[str, Any]]:
    platform = source["platform"]
    if platform == "greenhouse":
        payload = fetcher(greenhouse_url(source["board_token"]))
        return greenhouse_postings(source, payload, collected_at)

    region = source.get("region", "global")
    payload = fetcher(lever_url(source["site"], region))
    return lever_postings(source, payload, collected_at)


def load_sources(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise CollectionError(
            f"Sources file does not exist: {path}. Copy "
            "strategy/job_sources.example.json to strategy/job_sources.json "
            "and configure employer board identifiers."
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CollectionError(
            f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}."
        ) from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise CollectionError("Job sources must use schema_version 1.")
    sources = value.get("sources")
    if not isinstance(sources, list):
        raise CollectionError("Job sources must contain a sources array.")
    return [
        validate_source(source, index)
        for index, source in enumerate(sources)
        if not isinstance(source, dict) or source.get("enabled", True)
    ]


def output_name(posting: dict[str, Any]) -> str:
    identity = posting.get("external_job_id") or posting["posting_url"]
    suffix = slugify(str(identity))[-60:]
    return "-".join(
        (
            slugify(posting["company"])[:45],
            posting["platform"],
            suffix,
        )
    ) + ".json"


def write_postings(
    postings: list[dict[str, Any]],
    output_directory: Path,
) -> tuple[int, int]:
    output_directory.mkdir(parents=True, exist_ok=True)
    created = 0
    updated = 0
    for posting in postings:
        path = output_directory / output_name(posting)
        existed = path.exists()
        path.write_text(
            json.dumps(posting, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if existed:
            updated += 1
        else:
            created += 1
    return created, updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect public Greenhouse and Lever job postings."
    )
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES_PATH)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        sources = load_sources(args.sources)
        collected_at = datetime.now(timezone.utc).isoformat()
        postings: list[dict[str, Any]] = []
        for source in sources:
            postings.extend(collect_source(source, collected_at))

        if args.dry_run:
            print(
                f"Collected {len(postings)} public posting(s) from "
                f"{len(sources)} source(s)."
            )
            print("Dry run: no raw posting files were written.")
            return 0

        created, updated = write_postings(postings, args.output_directory)
        print(
            f"Collected {len(postings)} public posting(s) from "
            f"{len(sources)} source(s)."
        )
        print(f"Created: {created}; updated: {updated}.")
        return 0
    except CollectionError as exc:
        print(f"Collection failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from collect_job_postings import (
    CollectionError,
    collect_source,
    greenhouse_postings,
    greenhouse_url,
    html_to_text,
    lever_postings,
    lever_url,
    lever_description,
    load_sources,
    salary_period,
    write_postings,
)
from normalize_job_lead import build_job_lead
from validate_job_lead import load_json, validate_business_rules, validate_schema


COLLECTED_AT = "2026-07-19T20:00:00+00:00"
ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / (
    "hermes-skills/job-discovery/references/job-lead-schema.json"
)


class JobPostingCollectorTests(unittest.TestCase):
    def test_html_to_text_preserves_readable_blocks(self) -> None:
        result = html_to_text("<p>Build APIs &amp; tools.</p><ul><li>Python</li></ul>")
        self.assertEqual(result, "Build APIs & tools.\nPython")

    def test_greenhouse_url_requests_full_content(self) -> None:
        self.assertEqual(
            greenhouse_url("example company"),
            "https://boards-api.greenhouse.io/v1/boards/"
            "example%20company/jobs?content=true",
        )

    def test_greenhouse_response_maps_to_raw_contract(self) -> None:
        source = {
            "company": "Example AI",
            "platform": "greenhouse",
            "board_token": "example-ai",
        }
        payload = {
            "jobs": [
                {
                    "id": 123,
                    "title": "AI Engineer",
                    "absolute_url": "https://boards.greenhouse.io/example/jobs/123",
                    "content": "<p>Build Python AI systems.</p>",
                    "location": {"name": "Remote, Canada"},
                    "departments": [{"name": "Engineering"}],
                    "first_published": "2026-07-18T12:00:00Z",
                }
            ]
        }

        posting = greenhouse_postings(source, payload, COLLECTED_AT)[0]

        self.assertEqual(posting["company"], "Example AI")
        self.assertEqual(posting["external_job_id"], "123")
        self.assertEqual(posting["description_text"], "Build Python AI systems.")
        self.assertEqual(posting["location_raw"], "Remote, Canada")
        self.assertEqual(posting["department"], "Engineering")
        self.assertEqual(posting["posted_date"], "2026-07-18")

        lead = build_job_lead(posting, criteria_version=1)
        errors = validate_schema(lead, load_json(SCHEMA_PATH))
        errors.extend(validate_business_rules(lead))
        self.assertEqual(errors, [])

    def test_lever_url_supports_eu_region(self) -> None:
        self.assertEqual(
            lever_url("example", "eu"),
            "https://api.eu.lever.co/v0/postings/example?mode=json",
        )

    def test_salary_period_normalizes_lever_variants(self) -> None:
        self.assertEqual(salary_period("per-year-salary"), "year")
        self.assertEqual(salary_period("hourly"), "hour")
        self.assertIsNone(salary_period("project"))

    def test_lever_response_maps_salary_and_application_url(self) -> None:
        source = {
            "company": "Example AI",
            "platform": "lever",
            "site": "example-ai",
        }
        payload = [
            {
                "id": "abc-123",
                "text": "Backend Engineer, AI Platform",
                "descriptionPlain": "Build Python APIs for AI products.",
                "hostedUrl": "https://jobs.lever.co/example-ai/abc-123",
                "applyUrl": "https://jobs.lever.co/example-ai/abc-123/apply",
                "categories": {
                    "location": "Canada (Remote)",
                    "commitment": "Full-time",
                    "team": "Engineering",
                },
                "workplaceType": "remote",
                "salaryRange": {
                    "currency": "CAD",
                    "interval": "year",
                    "min": 120000,
                    "max": 150000,
                },
            }
        ]

        posting = lever_postings(source, payload, COLLECTED_AT)[0]

        self.assertEqual(posting["application_url"], payload[0]["applyUrl"])
        self.assertEqual(posting["workplace_type_raw"], "remote")
        self.assertEqual(posting["salary"]["minimum"], 120000)
        self.assertEqual(posting["salary"]["currency"], "CAD")

    def test_lever_description_uses_structured_fallbacks(self) -> None:
        description = lever_description(
            {
                "openingPlain": "Build useful products.",
                "lists": [
                    {
                        "text": "Requirements",
                        "content": "<li>Python</li><li>APIs</li>",
                    }
                ],
            }
        )
        self.assertEqual(
            description,
            "Build useful products.\nRequirements\nPython\nAPIs",
        )

    def test_lever_posting_without_description_is_skipped(self) -> None:
        postings = lever_postings(
            {"company": "Example", "platform": "lever"},
            [
                {
                    "id": "empty",
                    "text": "General Interest",
                    "hostedUrl": "https://jobs.lever.co/example/empty",
                    "categories": {},
                }
            ],
            COLLECTED_AT,
        )
        self.assertEqual(postings, [])

    def test_collect_source_uses_injected_fetcher(self) -> None:
        requested: list[str] = []

        def fetcher(url: str) -> dict[str, list[dict[str, object]]]:
            requested.append(url)
            return {"jobs": []}

        postings = collect_source(
            {
                "company": "Example AI",
                "platform": "greenhouse",
                "board_token": "example-ai",
            },
            COLLECTED_AT,
            fetcher=fetcher,
        )

        self.assertEqual(postings, [])
        self.assertEqual(requested, [greenhouse_url("example-ai")])

    def test_disabled_sources_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            path.write_text(
                """{
                  "schema_version": 1,
                  "sources": [
                    {
                      "company": "Disabled",
                      "platform": "greenhouse",
                      "board_token": "disabled",
                      "enabled": false
                    }
                  ]
                }""",
                encoding="utf-8",
            )
            self.assertEqual(load_sources(path), [])

    def test_unknown_platform_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            path.write_text(
                """{
                  "schema_version": 1,
                  "sources": [
                    {"company": "Example", "platform": "unknown"}
                  ]
                }""",
                encoding="utf-8",
            )
            with self.assertRaises(CollectionError):
                load_sources(path)

    def test_write_postings_updates_deterministic_file(self) -> None:
        posting = {
            "company": "Example AI",
            "platform": "lever",
            "external_job_id": "abc-123",
            "posting_url": "https://jobs.lever.co/example/abc-123",
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self.assertEqual(write_postings([posting], output), (1, 0))
            self.assertEqual(write_postings([posting], output), (0, 1))
            self.assertEqual(len(list(output.glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()

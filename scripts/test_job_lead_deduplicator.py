#!/usr/bin/env python3

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from deduplicate_job_leads import (
    choose_canonical,
    detect_duplicate,
    is_duplicate_candidate,
    locations_compatible,
    normalized_similarity,
    source_priority,
)
from normalize_job_lead import build_job_lead
from validate_job_lead import load_json


ROOT = Path(__file__).resolve().parent.parent

RAW_EXAMPLE_PATH = ROOT / (
    "hermes-skills/job-discovery/references/"
    "raw-job-posting-example.json"
)


class JobLeadDeduplicatorTests(unittest.TestCase):
    def build_example(self) -> dict:
        raw = load_json(RAW_EXAMPLE_PATH)

        return build_job_lead(
            raw=raw,
            criteria_version=1,
        )

    def test_same_canonical_url_is_exact_duplicate(self) -> None:
        first = self.build_example()
        second = copy.deepcopy(first)

        second["lead_id"] = "second-lead"
        second["source"]["platform"] = "linkedin"
        second["source"]["posting_url"] = (
            "https://example.com/careers/example-123"
            "?utm_source=linkedin"
        )

        match = detect_duplicate(first, second)

        self.assertIsNotNone(match)
        self.assertEqual(match.confidence, "exact")

    def test_same_external_job_id_is_exact_duplicate(self) -> None:
        first = self.build_example()
        second = copy.deepcopy(first)

        second["lead_id"] = "second-lead"
        second["source"]["canonical_url"] = (
            "https://jobs.example.com/positions/example-123"
        )
        second["source"]["posting_url"] = (
            second["source"]["canonical_url"]
        )

        match = detect_duplicate(first, second)

        self.assertIsNotNone(match)
        self.assertEqual(match.confidence, "exact")

    def test_different_companies_are_not_duplicates(self) -> None:
        first = self.build_example()
        second = copy.deepcopy(first)

        second["lead_id"] = "other-company-lead"
        second["identity"]["company"] = "Different AI"
        second["identity"]["normalized_company"] = (
            "different ai"
        )
        second["identity"]["external_job_id"] = None
        second["source"]["canonical_url"] = (
            "https://different.example/jobs/123"
        )
        second["source"]["posting_url"] = (
            second["source"]["canonical_url"]
        )

        match = detect_duplicate(first, second)

        self.assertIsNone(match)
        self.assertFalse(is_duplicate_candidate(first, second))

    def test_same_company_is_a_duplicate_candidate(self) -> None:
        first = self.build_example()
        second = copy.deepcopy(first)
        second["lead_id"] = "second-lead"
        second["source"]["canonical_url"] = "https://example.com/jobs/other"

        self.assertTrue(is_duplicate_candidate(first, second))

    def test_company_source_has_higher_priority(self) -> None:
        self.assertGreater(
            source_priority(
                {
                    "source": {
                        "platform": "company_careers"
                    }
                }
            ),
            source_priority(
                {
                    "source": {
                        "platform": "linkedin"
                    }
                }
            ),
        )

    def test_company_posting_becomes_canonical(self) -> None:
        company_lead = self.build_example()
        linkedin_lead = copy.deepcopy(company_lead)

        linkedin_lead["lead_id"] = "linkedin-copy"
        linkedin_lead["source"]["platform"] = "linkedin"

        canonical, duplicate = choose_canonical(
            company_lead,
            linkedin_lead,
        )

        self.assertEqual(
            canonical["lead_id"],
            company_lead["lead_id"],
        )
        self.assertEqual(
            duplicate["lead_id"],
            "linkedin-copy",
        )

    def test_applied_record_remains_canonical_across_sources(self) -> None:
        company = self.build_example()
        company["lead_id"] = "company-copy"
        company["source"]["platform"] = "company_careers"

        applied = copy.deepcopy(company)
        applied["lead_id"] = "applied-linkedin-copy"
        applied["source"]["platform"] = "linkedin"
        applied["status"]["lead_status"] = "applied"

        canonical, duplicate = choose_canonical(company, applied)

        self.assertEqual(canonical["lead_id"], "applied-linkedin-copy")
        self.assertEqual(duplicate["lead_id"], "company-copy")

    def test_remote_and_on_site_are_incompatible(self) -> None:
        first = self.build_example()
        second = copy.deepcopy(first)

        first["location"]["workplace_type"] = "remote"
        second["location"]["workplace_type"] = "on_site"

        self.assertFalse(
            locations_compatible(first, second)
        )

    def test_similar_roles_score_highly(self) -> None:
        similarity = normalized_similarity(
            "ai application engineer",
            "ai applications engineer",
        )

        self.assertGreaterEqual(similarity, 0.90)

    def test_separate_external_ids_are_not_enough_to_merge(self) -> None:
        first = self.build_example()
        second = copy.deepcopy(first)

        second["lead_id"] = "separate-opening"
        second["identity"]["external_job_id"] = "example-456"
        second["source"]["canonical_url"] = (
            "https://example.com/careers/example-456"
        )
        second["source"]["posting_url"] = (
            second["source"]["canonical_url"]
        )
        second["content"]["description_text"] = (
            "A different software engineering position with "
            "different responsibilities and requirements."
        )
        second["content"]["description_hash"] = (
            "0" * 64
        )

        match = detect_duplicate(first, second)

        self.assertIsNone(match)

    def test_same_description_different_roles_are_not_exact_duplicates(self) -> None:
        first = self.build_example()
        second = copy.deepcopy(first)
        second["lead_id"] = "marketing-opening"
        second["identity"]["role"] = "Marketing Director"
        second["identity"]["normalized_role"] = "marketing director"
        second["identity"]["external_job_id"] = "marketing-123"
        second["source"]["canonical_url"] = "https://example.com/jobs/marketing"
        second["source"]["posting_url"] = second["source"]["canonical_url"]

        self.assertIsNone(detect_duplicate(first, second))

    def test_different_explicit_locations_are_incompatible(self) -> None:
        first = self.build_example()
        second = copy.deepcopy(first)
        first["location"]["raw"] = "Canada (Remote)"
        second["location"]["raw"] = "United States (Remote)"

        self.assertFalse(locations_compatible(first, second))


if __name__ == "__main__":
    unittest.main()

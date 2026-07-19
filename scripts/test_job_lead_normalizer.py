#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from normalize_job_lead import (
    build_job_lead,
    canonicalize_url,
    description_hash,
    infer_customer_facing_level,
    infer_primary_function,
    infer_workplace_type,
)
from validate_job_lead import (
    load_json,
    validate_business_rules,
    validate_schema,
)


ROOT = Path(__file__).resolve().parent.parent

SCHEMA_PATH = ROOT / (
    "hermes-skills/job-discovery/references/"
    "job-lead-schema.json"
)

RAW_EXAMPLE_PATH = ROOT / (
    "hermes-skills/job-discovery/references/"
    "raw-job-posting-example.json"
)


class JobLeadNormalizerTests(unittest.TestCase):
    def test_canonical_url_removes_tracking_parameters(self) -> None:
        result = canonicalize_url(
            "https://example.com/jobs/123"
            "?utm_source=linkedin&job_id=123#apply"
        )

        self.assertEqual(
            result,
            "https://example.com/jobs/123?job_id=123",
        )

    def test_primary_function_detects_ai_engineering(self) -> None:
        result = infer_primary_function(
            "AI Application Engineer",
            "Build production Python and LLM applications.",
        )

        self.assertEqual(result, "ai_engineering")

    def test_workplace_type_detects_remote(self) -> None:
        result = infer_workplace_type(
            "Remote",
            "This role may be performed anywhere in Canada.",
        )

        self.assertEqual(result, "remote")

    def test_customer_facing_level_detects_low(self) -> None:
        result = infer_customer_facing_level(
            "AI Application Engineer",
            (
                "This role is primarily hands-on engineering. "
                "You will occasionally meet with customers."
            ),
        )

        self.assertEqual(result, "low")

    def test_description_hash_normalizes_whitespace(self) -> None:
        first = description_hash("Build AI systems.")
        second = description_hash("Build   AI\nsystems.")

        self.assertEqual(first, second)

    def test_example_normalizes_to_valid_job_lead(self) -> None:
        raw = load_json(RAW_EXAMPLE_PATH)
        schema = load_json(SCHEMA_PATH)

        lead = build_job_lead(
            raw=raw,
            criteria_version=1,
        )

        errors = validate_schema(lead, schema)
        errors.extend(validate_business_rules(lead))

        self.assertEqual(errors, [])

    def test_normalized_lead_starts_unscored(self) -> None:
        raw = load_json(RAW_EXAMPLE_PATH)

        lead = build_job_lead(
            raw=raw,
            criteria_version=1,
        )

        self.assertIsNone(
            lead["discovery"]["preliminary_score"]
        )
        self.assertEqual(
            lead["discovery"]["hard_filter_result"],
            "not_evaluated",
        )
        self.assertEqual(
            lead["status"]["lead_status"],
            "new",
        )


if __name__ == "__main__":
    unittest.main()

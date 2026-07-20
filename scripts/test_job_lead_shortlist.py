#!/usr/bin/env python3

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from filter_job_leads import apply_filter_decision, evaluate_hard_filters
from normalize_job_lead import build_job_lead
from score_job_leads import apply_score_result, calculate_score
from surface_job_leads import lead_bucket, render_shortlist
from validate_job_lead import load_json


ROOT = Path(__file__).resolve().parent.parent
RAW_EXAMPLE_PATH = ROOT / (
    "hermes-skills/job-discovery/references/raw-job-posting-example.json"
)
CRITERIA_PATH = ROOT / "strategy/job_search_criteria.json"


class JobLeadShortlistTests(unittest.TestCase):
    def setUp(self) -> None:
        raw = load_json(RAW_EXAMPLE_PATH)
        self.criteria = load_json(CRITERIA_PATH)
        self.lead = build_job_lead(raw=raw, criteria_version=1)
        decision = evaluate_hard_filters(self.lead, self.criteria)
        apply_filter_decision(self.lead, decision)
        result = calculate_score(self.lead, self.criteria)
        apply_score_result(self.lead, result, self.criteria)

    def test_recommended_lead_is_in_full_analysis_bucket(self) -> None:
        self.assertEqual(lead_bucket(self.lead), "full_analysis")

    def test_manual_review_is_not_presented_as_recommended(self) -> None:
        manual = copy.deepcopy(self.lead)
        manual["discovery"]["hard_filter_result"] = "manual_review"
        manual["discovery"]["full_analysis_recommended"] = False
        manual["discovery"]["hard_filter_reasons"] = [
            "Canadian hiring eligibility is not confirmed."
        ]
        manual["status"]["lead_status"] = "new"

        report = render_shortlist([manual])

        self.assertEqual(lead_bucket(manual), "manual_review")
        self.assertIn("## Manual Eligibility Review", report)
        self.assertIn("Canadian hiring eligibility", report)
        self.assertIn("Recommended for full analysis: 0", report)

    def test_report_orders_recommended_leads_by_score(self) -> None:
        lower = copy.deepcopy(self.lead)
        lower["lead_id"] = "lower-score"
        lower["identity"]["company"] = "Lower Score Co"
        lower["identity"]["normalized_company"] = "lower score co"
        lower["discovery"]["preliminary_score"] = 71

        higher = copy.deepcopy(self.lead)
        higher["lead_id"] = "higher-score"
        higher["identity"]["company"] = "Higher Score Co"
        higher["identity"]["normalized_company"] = "higher score co"
        higher["discovery"]["preliminary_score"] = 95

        report = render_shortlist([lower, higher])

        self.assertLess(
            report.index("Higher Score Co"),
            report.index("Lower Score Co"),
        )

    def test_archived_duplicate_is_separated(self) -> None:
        archived = copy.deepcopy(self.lead)
        archived["status"]["lead_status"] = "archived"
        archived["status"]["duplicate_of"] = self.lead["lead_id"]

        report = render_shortlist([archived])

        self.assertEqual(lead_bucket(archived), "archived")
        self.assertIn("Archived duplicates: 1", report)

    def test_report_includes_source_and_compensation(self) -> None:
        report = render_shortlist([self.lead])

        self.assertIn(self.lead["source"]["posting_url"], report)
        self.assertIn("CAD", report)
        self.assertIn("110,000", report)


if __name__ == "__main__":
    unittest.main()

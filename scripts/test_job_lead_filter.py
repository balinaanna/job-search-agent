#!/usr/bin/env python3

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from filter_job_leads import (
    apply_filter_decision,
    evaluate_hard_filters,
    filter_leads,
)
from normalize_job_lead import build_job_lead
from validate_job_lead import load_json


ROOT = Path(__file__).resolve().parent.parent
RAW_EXAMPLE_PATH = ROOT / (
    "hermes-skills/job-discovery/references/"
    "raw-job-posting-example.json"
)
CRITERIA_PATH = ROOT / "strategy/job_search_criteria.json"


class JobLeadFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        raw = load_json(RAW_EXAMPLE_PATH)
        self.lead = build_job_lead(raw=raw, criteria_version=1)
        self.criteria = load_json(CRITERIA_PATH)

    def test_eligible_canadian_engineering_role_passes(self) -> None:
        decision = evaluate_hard_filters(self.lead, self.criteria)
        self.assertEqual(decision.result, "pass")
        self.assertEqual(decision.reasons, ())

    def test_confirmed_inability_to_hire_in_canada_fails(self) -> None:
        self.lead["location"]["can_hire_in_canada"] = False
        decision = evaluate_hard_filters(self.lead, self.criteria)
        self.assertEqual(decision.result, "fail")
        self.assertIn("cannot hire in Canada", decision.reasons[0])

    def test_unknown_canadian_eligibility_requires_review(self) -> None:
        self.lead["location"]["can_hire_in_canada"] = None
        decision = evaluate_hard_filters(self.lead, self.criteria)
        self.assertEqual(decision.result, "manual_review")

    def test_excluded_title_fails(self) -> None:
        self.lead["position"]["title"] = "Senior Account Manager"
        decision = evaluate_hard_filters(self.lead, self.criteria)
        self.assertEqual(decision.result, "fail")
        self.assertIn("title", decision.reasons[0])

    def test_closed_posting_fails(self) -> None:
        self.lead["application"]["posting_status"] = "closed"
        decision = evaluate_hard_filters(self.lead, self.criteria)
        self.assertEqual(decision.result, "fail")

    def test_required_driving_fails(self) -> None:
        self.lead["requirements"]["driving_required"] = True
        decision = evaluate_hard_filters(self.lead, self.criteria)
        self.assertEqual(decision.result, "fail")

    def test_on_site_toronto_role_fails(self) -> None:
        self.lead["location"].update(
            {
                "workplace_type": "on_site",
                "country": "Canada",
                "region": "Ontario",
                "city": "Toronto",
            }
        )
        decision = evaluate_hard_filters(self.lead, self.criteria)
        self.assertEqual(decision.result, "fail")

    def test_on_site_vancouver_role_passes(self) -> None:
        self.lead["location"].update(
            {
                "workplace_type": "on_site",
                "country": "Canada",
                "region": "British Columbia",
                "city": "Vancouver",
            }
        )
        decision = evaluate_hard_filters(self.lead, self.criteria)
        self.assertEqual(decision.result, "pass")

    def test_part_time_under_25_hours_fails(self) -> None:
        self.lead["employment"]["employment_type"] = "part_time"
        self.lead["employment"]["schedule"] = "20 hours per week"
        decision = evaluate_hard_filters(self.lead, self.criteria)
        self.assertEqual(decision.result, "fail")

    def test_unclear_part_time_hours_require_review(self) -> None:
        self.lead["employment"]["employment_type"] = "part_time"
        self.lead["employment"]["schedule"] = "Part-time"
        decision = evaluate_hard_filters(self.lead, self.criteria)
        self.assertEqual(decision.result, "manual_review")

    def test_fail_updates_lead_status(self) -> None:
        self.lead["requirements"]["clearance_required"] = True
        decision = evaluate_hard_filters(self.lead, self.criteria)
        apply_filter_decision(self.lead, decision)
        self.assertEqual(
            self.lead["discovery"]["hard_filter_result"],
            "fail",
        )
        self.assertFalse(
            self.lead["discovery"]["full_analysis_recommended"]
        )
        self.assertEqual(self.lead["status"]["lead_status"], "rejected")

    def test_archived_duplicates_are_not_re_evaluated(self) -> None:
        archived = copy.deepcopy(self.lead)
        archived["status"]["lead_status"] = "archived"
        archived["status"]["duplicate_of"] = "canonical-lead"
        decisions = filter_leads(
            [(Path("unused.json"), archived)],
            self.criteria,
            dry_run=True,
        )
        self.assertEqual(decisions, [])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from filter_job_leads import apply_filter_decision, evaluate_hard_filters
from normalize_job_lead import build_job_lead
from score_job_leads import (
    apply_score_result,
    calculate_score,
    score_leads,
    score_title_alignment,
)
from validate_job_lead import JobLeadValidationError, load_json


ROOT = Path(__file__).resolve().parent.parent
RAW_EXAMPLE_PATH = ROOT / (
    "hermes-skills/job-discovery/references/raw-job-posting-example.json"
)
CRITERIA_PATH = ROOT / "strategy/job_search_criteria.json"


class JobLeadScorerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.criteria = load_json(CRITERIA_PATH)
        raw = load_json(RAW_EXAMPLE_PATH)
        self.lead = build_job_lead(raw=raw, criteria_version=1)
        decision = evaluate_hard_filters(self.lead, self.criteria)
        apply_filter_decision(self.lead, decision)

    def test_ai_application_engineer_scores_for_full_analysis(self) -> None:
        result = calculate_score(self.lead, self.criteria)
        self.assertGreaterEqual(result.preliminary_score, 70)
        self.assertTrue(result.full_analysis_recommended)

    def test_exact_primary_title_keeps_configured_priority(self) -> None:
        score = score_title_alignment(self.lead, self.criteria)
        self.assertEqual(score, 98)

    def test_ai_role_scores_above_business_analysis_role(self) -> None:
        business_lead = copy.deepcopy(self.lead)
        business_lead["position"]["title"] = "Business Systems Analyst"
        business_lead["position"]["primary_function"] = "business_analysis"
        business_lead["requirements"]["technical_skills"] = ["SQL"]
        business_lead["requirements"]["domain_skills"] = ["Data analytics"]
        business_lead["content"]["description_text"] = (
            "Analyze business processes, document requirements, and use SQL."
        )
        ai_score = calculate_score(self.lead, self.criteria).preliminary_score
        business_score = calculate_score(
            business_lead,
            self.criteria,
        ).preliminary_score
        self.assertGreater(ai_score, business_score)

    def test_primary_customer_facing_work_receives_penalty(self) -> None:
        self.lead["requirements"]["customer_facing_level"] = (
            "primary_responsibility"
        )
        result = calculate_score(self.lead, self.criteria)
        names = {penalty["name"] for penalty in result.penalties}
        self.assertIn("primarily_customer_facing", names)

    def test_support_role_receives_support_penalty(self) -> None:
        self.lead["position"]["primary_function"] = "support"
        result = calculate_score(self.lead, self.criteria)
        names = {penalty["name"] for penalty in result.penalties}
        self.assertIn("primarily_support", names)

    def test_manual_review_cannot_recommend_full_analysis(self) -> None:
        self.lead["discovery"]["hard_filter_result"] = "manual_review"
        result = calculate_score(self.lead, self.criteria)
        self.assertFalse(result.full_analysis_recommended)

    def test_unfiltered_lead_cannot_be_scored(self) -> None:
        self.lead["discovery"]["hard_filter_result"] = "not_evaluated"
        with self.assertRaises(JobLeadValidationError):
            calculate_score(self.lead, self.criteria)

    def test_score_result_populates_contract_fields(self) -> None:
        result = calculate_score(self.lead, self.criteria)
        apply_score_result(self.lead, result, self.criteria)
        discovery = self.lead["discovery"]
        self.assertEqual(
            discovery["preliminary_score"],
            result.preliminary_score,
        )
        self.assertTrue(
            all(
                value is not None
                for value in discovery["score_components"].values()
            )
        )

    def test_below_discovery_threshold_is_rejected(self) -> None:
        low_result = calculate_score(self.lead, self.criteria)
        low_result = type(low_result)(
            preliminary_score=20,
            components=low_result.components,
            penalties=low_result.penalties,
            full_analysis_recommended=False,
        )
        apply_score_result(self.lead, low_result, self.criteria)
        self.assertEqual(self.lead["status"]["lead_status"], "rejected")

    def test_ranking_is_score_descending(self) -> None:
        second = copy.deepcopy(self.lead)
        second["lead_id"] = "lower-ranked"
        second["position"]["title"] = "Business Systems Analyst"
        second["position"]["primary_function"] = "business_analysis"
        second["requirements"]["technical_skills"] = ["SQL"]
        second["content"]["description_text"] = "Document business requirements."
        results = score_leads(
            [(Path("first.json"), self.lead), (Path("second.json"), second)],
            self.criteria,
            dry_run=True,
        )
        self.assertGreaterEqual(
            results[0][1].preliminary_score,
            results[1][1].preliminary_score,
        )

    def test_scoring_does_not_reset_application_status(self) -> None:
        self.lead["status"]["lead_status"] = "application_started"
        result = calculate_score(self.lead, self.criteria)
        apply_score_result(self.lead, result, self.criteria)
        self.assertEqual(
            self.lead["status"]["lead_status"],
            "application_started",
        )


if __name__ == "__main__":
    unittest.main()

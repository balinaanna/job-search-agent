#!/usr/bin/env python3

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from surface_fit_queue import FitResult, join_results, render_queue
from validate_job_lead import load_json


ROOT = Path(__file__).resolve().parent.parent
LEAD_PATH = ROOT / "hermes-skills/job-discovery/references/job-lead-example.json"


def analysis_for(lead: dict, score: int, recommendation: str) -> dict:
    components = [20, 14, 12, 5, 4, 5]
    assert sum(components) == score
    return {
        "job": {
            "title": lead["identity"]["role"],
            "company": lead["identity"]["company"],
            "source": lead["source"]["posting_url"],
        },
        "recommendation": recommendation,
        "score": {
            "responsibilities_match": components[0],
            "evidence_strength": components[1],
            "people_facing_alignment": components[2],
            "technology_match": components[3],
            "seniority_match": components[4],
            "logistics_match": components[5],
            "total_score": score,
        },
        "summary": {
            "strongest_reasons": ["Relevant verified experience."],
            "main_risk": "A material requirement is unsupported.",
            "recommended_next_action": "Review as a stretch role.",
        },
    }


class FitQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lead = load_json(LEAD_PATH)
        self.lead["discovery"]["preliminary_score"] = 96
        self.lead["discovery"]["full_analysis_recommended"] = True

    def test_analysis_supersedes_inflated_discovery_score(self) -> None:
        analysis = analysis_for(self.lead, 60, "selective_apply")
        results, awaiting = join_results(
            [self.lead], [(Path("analysis.json"), analysis)]
        )
        report = render_queue(results, awaiting)

        self.assertIn("Selective or Stretch Apply", report)
        self.assertIn("60/100", report)
        self.assertIn("Discovery score: 96; adjustment -36", report)
        self.assertNotIn("Awaiting full analysis: 1", report)

    def test_unanalyzed_recommended_lead_waits_for_analysis(self) -> None:
        results, awaiting = join_results([self.lead], [])
        report = render_queue(results, awaiting)

        self.assertEqual(results, [])
        self.assertEqual(awaiting, [self.lead])
        self.assertIn("Awaiting full analysis: 1", report)
        self.assertIn("before considering an application", report)

    def test_final_scores_determine_order(self) -> None:
        second = copy.deepcopy(self.lead)
        second["lead_id"] = "second"
        second["identity"]["company"] = "Second Company"
        second["identity"]["normalized_company"] = "second company"
        second["source"]["posting_url"] = "https://example.com/second"
        lower = analysis_for(self.lead, 60, "selective_apply")
        higher = analysis_for(second, 60, "selective_apply")
        higher["score"]["responsibilities_match"] = 25
        higher["score"]["total_score"] = 65
        higher["recommendation"] = "apply"

        results, _ = join_results(
            [self.lead, second],
            [(Path("lower.json"), lower), (Path("higher.json"), higher)],
        )

        self.assertEqual(results[0].lead["lead_id"], "second")

    def test_reanalysis_replaces_legacy_analysis_for_same_job(self) -> None:
        old = analysis_for(self.lead, 60, "selective_apply")
        current = copy.deepcopy(old)
        current["score"]["responsibilities_match"] = 23
        current["score"]["total_score"] = 63
        results, awaiting = join_results([
            self.lead
        ], [
            (Path("legacy-job/analysis.json"), old),
            (Path(self.lead["lead_id"]) / "analysis.json", current),
        ])
        self.assertEqual(1, len(results))
        self.assertEqual(63, results[0].analysis["score"]["total_score"])
        self.assertEqual([], awaiting)


if __name__ == "__main__":
    unittest.main()

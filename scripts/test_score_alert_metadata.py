import unittest

from score_alert_metadata import score_alert_metadata


CRITERIA = {
    "search_strategy": {
        "primary_targets": [{"title": "AI Engineer", "priority_score": 100}],
        "secondary_targets": [{"title": "Data Engineer", "priority_score": 80}],
        "conditional_targets": [],
        "excluded_titles": ["Account Executive"],
    }
}


class AlertMetadataScoreTests(unittest.TestCase):
    def test_scores_matching_title_without_claiming_verified_fit(self) -> None:
        result = score_alert_metadata({"title": "Senior AI Engineer"}, CRITERIA)
        self.assertGreaterEqual(result["score"], 75)
        self.assertEqual(result["basis"], "Title only")
        self.assertIn("without opening", result["limitations"][0])

    def test_explicitly_excluded_title_scores_low(self) -> None:
        result = score_alert_metadata({"title": "Enterprise Account Executive"}, CRITERIA)
        self.assertEqual(result["score"], 5)

    def test_unknown_title_stays_conservative(self) -> None:
        result = score_alert_metadata({"title": "Office Coordinator"}, CRITERIA)
        self.assertLess(result["score"], 55)

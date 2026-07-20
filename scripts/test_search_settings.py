import json
import tempfile
import unittest
from pathlib import Path

from search_settings import load_search_settings, save_search_settings


class SearchSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.criteria = root / "criteria.json"
        self.sources = root / "sources.json"
        self.schedule = root / "schedule.json"
        self.criteria.write_text(json.dumps({
            "strategy_version": 3,
            "search_strategy": {"primary_targets": [{"title": "AI Engineer", "priority_score": 100, "reasons": ["Current target"]}]},
            "locations": {"preferred": ["Remote within Canada"]},
        }))
        self.sources.write_text(json.dumps({"schema_version": 1, "sources": [
            {"company": "Example", "platform": "greenhouse", "board_token": "example", "enabled": True},
            {"company": "Other", "platform": "lever", "site": "other", "enabled": True},
        ]}))

    def tearDown(self):
        self.temp.cleanup()

    def test_saves_safe_search_preferences(self):
        result = save_search_settings({
            "roles": ["AI Engineer", "Backend Engineer"],
            "locations": ["Vancouver, BC"],
            "frequency": "daily",
            "enabled_source_ids": ["greenhouse:example"],
        }, self.criteria, self.sources, self.schedule)
        self.assertEqual(result["frequency"], "daily")
        self.assertEqual(result["roles"], ["AI Engineer", "Backend Engineer"])
        self.assertEqual(json.loads(self.criteria.read_text())["strategy_version"], 4)
        self.assertFalse(result["sources"][1]["enabled"])

    def test_rejects_empty_or_unknown_selections(self):
        with self.assertRaisesRegex(ValueError, "between 1 and 20"):
            save_search_settings({"roles": [], "locations": ["Canada"], "frequency": "manual", "enabled_source_ids": ["greenhouse:example"]}, self.criteria, self.sources, self.schedule)
        with self.assertRaisesRegex(ValueError, "unknown"):
            save_search_settings({"roles": ["AI Engineer"], "locations": ["Canada"], "frequency": "manual", "enabled_source_ids": ["greenhouse:missing"]}, self.criteria, self.sources, self.schedule)

    def test_defaults_to_manual_schedule(self):
        self.assertEqual(load_search_settings(self.criteria, self.sources, self.schedule)["frequency"], "manual")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from normalize_job_lead import build_job_lead
from run_job_discovery import copy_status_for_refresh, refreshed_lead, run_pipeline
from validate_job_lead import load_json


ROOT = Path(__file__).resolve().parent.parent
RAW_EXAMPLE_PATH = ROOT / (
    "hermes-skills/job-discovery/references/raw-job-posting-example.json"
)
CRITERIA_PATH = ROOT / "strategy/job_search_criteria.json"
SCHEMA_PATH = ROOT / (
    "hermes-skills/job-discovery/references/job-lead-schema.json"
)


class JobDiscoveryPipelineTests(unittest.TestCase):
    def test_refresh_preserves_workflow_state_and_first_seen(self) -> None:
        raw = load_json(RAW_EXAMPLE_PATH)
        existing = build_job_lead(raw, criteria_version=1)
        existing["source"]["first_seen_at"] = "2026-07-01T10:00:00-07:00"
        existing["status"]["lead_status"] = "applied"
        existing["status"]["reviewed"] = True

        changed_raw = copy.deepcopy(raw)
        changed_raw["description_text"] += " Updated by the employer."
        fresh = build_job_lead(changed_raw, criteria_version=1)

        merged = refreshed_lead(existing, fresh)

        self.assertEqual(merged["status"]["lead_status"], "applied")
        self.assertTrue(merged["status"]["reviewed"])
        self.assertEqual(
            merged["source"]["first_seen_at"],
            "2026-07-01T10:00:00-07:00",
        )
        self.assertIn("Updated by the employer", merged["content"]["description_text"])

    def test_pipeline_creates_ranked_shortlist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_directory = root / "raw"
            leads_directory = root / "leads"
            shortlist_path = leads_directory / "shortlist.md"
            action_queue_path = leads_directory / "action-queue.md"
            analyses_directory = root / "analyses"
            raw_directory.mkdir()
            raw = load_json(RAW_EXAMPLE_PATH)
            (raw_directory / "example.json").write_text(
                json.dumps(raw), encoding="utf-8"
            )

            summary = run_pipeline(
                raw_directory,
                leads_directory,
                shortlist_path,
                CRITERIA_PATH,
                SCHEMA_PATH,
                action_queue_path,
                analyses_directory,
                ROOT / "profile/evidence.yaml",
            )

            self.assertEqual(summary["created"], 1)
            self.assertEqual(summary["full_analysis"], 1)
            self.assertTrue(shortlist_path.exists())
            self.assertTrue(action_queue_path.exists())
            report = shortlist_path.read_text(encoding="utf-8")
            self.assertIn("Recommended for Full Job Fit Analysis", report)
            self.assertIn("Example AI", report)

    def test_automatic_duplicate_is_reconsidered_on_refresh(self) -> None:
        status = {
            "lead_status": "archived",
            "duplicate_of": "old-canonical",
            "reviewed": False,
            "notes": [
                "Deduplicated automatically: old rule. Confidence=exact; score=1.0000.",
                "Keep this user note.",
            ],
        }
        refreshed = copy_status_for_refresh(status)
        self.assertEqual(refreshed["lead_status"], "new")
        self.assertIsNone(refreshed["duplicate_of"])
        self.assertEqual(refreshed["notes"], ["Keep this user note."])

    def test_pipeline_refreshes_existing_lead(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_directory = root / "raw"
            leads_directory = root / "leads"
            shortlist_path = leads_directory / "shortlist.md"
            action_queue_path = leads_directory / "action-queue.md"
            analyses_directory = root / "analyses"
            raw_directory.mkdir()
            raw = load_json(RAW_EXAMPLE_PATH)
            raw_path = raw_directory / "example.json"
            raw_path.write_text(json.dumps(raw), encoding="utf-8")

            run_pipeline(
                raw_directory,
                leads_directory,
                shortlist_path,
                CRITERIA_PATH,
                SCHEMA_PATH,
                action_queue_path,
                analyses_directory,
                ROOT / "profile/evidence.yaml",
            )
            summary = run_pipeline(
                raw_directory,
                leads_directory,
                shortlist_path,
                CRITERIA_PATH,
                SCHEMA_PATH,
                action_queue_path,
                analyses_directory,
                ROOT / "profile/evidence.yaml",
            )

            self.assertEqual(summary["created"], 0)
            self.assertEqual(summary["refreshed"], 1)


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from collect_job_postings import CollectionError
from safe_capture_enrichment import enrich_alert_posting


class SafeCaptureEnrichmentTests(unittest.TestCase):
    def test_enriches_configured_greenhouse_posting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "sources.json"
            sources.write_text(json.dumps({"schema_version": 1, "sources": [{"company": "Acme", "platform": "greenhouse", "board_token": "acme", "enabled": True}]}))
            posting = enrich_alert_posting(
                {"posting_url": "https://job-boards.greenhouse.io/acme/jobs/12345"},
                sources,
                root / "raw",
                "2026-07-21T00:00:00+00:00",
                fetcher=lambda _: {"id": 12345, "title": "Platform Engineer", "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/12345", "content": "<p>" + ("Build reliable systems with careful testing and documentation. " * 5) + "</p>", "location": {"name": "Canada"}},
            )
            self.assertEqual(posting["company"], "Acme")
            self.assertEqual(len(list((root / "raw").glob("*.json"))), 1)

    def test_rejects_unreviewed_ats_account(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sources = Path(directory) / "sources.json"
            sources.write_text(json.dumps({"schema_version": 1, "sources": []}))
            with self.assertRaisesRegex(CollectionError, "not been reviewed"):
                enrich_alert_posting({"posting_url": "https://jobs.lever.co/unknown/abc"}, sources, Path(directory) / "raw", "now", fetcher=lambda _: {})

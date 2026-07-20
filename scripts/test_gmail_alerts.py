import tempfile
import unittest
from pathlib import Path

from gmail_alerts import load_config, save_config, source_from_message
from job_alert_inbox import AlertInboxStore


class GmailAlertsTests(unittest.TestCase):
    def test_config_defaults_disconnected_and_saves_without_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gmail.json"
            self.assertFalse(load_config(path)["connected"])
            result = save_config(path, "Anna@Gmail.com", 15)
            self.assertEqual(result["email"], "anna@gmail.com")
            self.assertNotIn("password", path.read_text().casefold())

    def test_identifies_supported_alert_senders(self):
        self.assertEqual(source_from_message("jobs-noreply@linkedin.com", "New jobs"), "linkedin")
        self.assertEqual(source_from_message("alert@indeed.com", "Jobs"), "indeed")
        self.assertEqual(source_from_message("alerts@eluta.ca", "New roles"), "eluta")
        self.assertIsNone(source_from_message("person@example.com", "Hello"))

    def test_tracks_processed_gmail_uids(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AlertInboxStore(Path(directory) / "jobs.db")
            self.assertFalse(store.gmail_processed("42")); store.mark_gmail_processed("42"); self.assertTrue(store.gmail_processed("42")); store.close()


if __name__ == "__main__": unittest.main()

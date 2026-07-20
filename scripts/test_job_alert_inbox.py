import tempfile
import unittest
from pathlib import Path

from job_alert_inbox import AlertInboxStore, parse_alert, save_captured_posting


class JobAlertInboxTests(unittest.TestCase):
    def test_parses_and_canonicalizes_supported_alerts(self):
        linkedin = parse_alert("linkedin", '<a href="https://www.linkedin.com/jobs/view/12345/?tracking=x">Applied AI Engineer</a>')
        indeed = parse_alert("indeed", '<a href="https://ca.indeed.com/rc/clk?jk=abc123&from=alert">Backend AI Engineer</a>')
        eluta = parse_alert("eluta", '<a href="https://www.eluta.ca/spl/software-engineer-abc123">Software Engineer</a>')
        self.assertEqual(linkedin[0]["posting_url"], "https://www.linkedin.com/jobs/view/12345")
        self.assertEqual(indeed[0]["posting_url"], "https://ca.indeed.com/viewjob?jk=abc123")
        self.assertEqual(eluta[0]["title"], "Software Engineer")

    def test_deduplicates_imported_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AlertInboxStore(Path(directory) / "jobs.db")
            content = '<a href="https://www.linkedin.com/jobs/view/12345">AI Engineer</a>'
            self.assertEqual(store.import_alert("linkedin", content)["added"], 1)
            result = store.import_alert("linkedin", content)
            self.assertEqual(result["added"], 0); self.assertEqual(result["duplicates"], 1)
            store.close()

    def test_rejects_empty_or_unknown_alerts(self):
        with self.assertRaisesRegex(ValueError, "Source"):
            parse_alert("other", "email")
        with self.assertRaisesRegex(ValueError, "Paste"):
            parse_alert("indeed", "")

    def test_saves_complete_user_captured_posting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = save_captured_posting({"source": "linkedin", "company": "Example AI", "role": "AI Engineer", "posting_url": "https://www.linkedin.com/jobs/view/12345?tracking=x", "description_text": "Build trustworthy AI products. " * 20, "location_raw": "Canada (Remote)"}, Path(directory))
            self.assertTrue(path.exists())
            self.assertIn('"platform": "linkedin"', path.read_text())

    def test_rejects_incomplete_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "complete job description"):
                save_captured_posting({"source": "eluta", "company": "Example", "role": "Engineer", "posting_url": "https://www.eluta.ca/spl/job-123", "description_text": "Too short"}, Path(directory))


if __name__ == "__main__": unittest.main()

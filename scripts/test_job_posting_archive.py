import unittest

from workflow_api import archived_posting


class JobPostingArchiveTests(unittest.TestCase):
    def test_preserves_interview_reference_details(self):
        lead = {"lead_id": "lead-1", "identity": {"company": "Example"}, "position": {"title": "AI Engineer"}, "content": {"description_text": "Complete job description", "description_hash": "abc"}, "location": {"raw": "Canada", "workplace_type": "remote"}, "employment": {"employment_type": "full_time", "salary": {"minimum": 100000}}, "application": {"posted_date": "2026-07-01"}, "source": {"collected_at": "2026-07-21T00:00:00+00:00", "platform": "linkedin", "posting_url": "https://example.test/job"}}
        archive = archived_posting(lead)
        self.assertEqual(archive["description"], "Complete job description")
        self.assertEqual(archive["captured_at"], "2026-07-21T00:00:00+00:00")
        self.assertEqual(archive["original_url"], "https://example.test/job")


if __name__ == "__main__":
    unittest.main()

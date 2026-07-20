#!/usr/bin/env python3

import unittest
from datetime import date

from application_tracker import initial_tracker, update_tracker


class ApplicationTrackerTests(unittest.TestCase):
    def test_initial_tracker_has_follow_up_and_confirmation(self) -> None:
        tracker = initial_tracker("lead-1", "Acme", "Analyst", "Application received")
        self.assertEqual(tracker["application_status"], "submitted")
        self.assertEqual(tracker["confirmation_evidence"], "Application received")
        date.fromisoformat(tracker["follow_up_date"])

    def test_status_update_is_audited(self) -> None:
        tracker = initial_tracker("lead-1", "Acme", "Analyst", "Received")
        updated = update_tracker(tracker, {"application_status": "interview", "confirmation_reference": "ABC-123", "follow_up_date": "2026-08-01", "expected_response_date": "2026-07-28", "interview_stage": "Recruiter screen", "next_action": "Prepare stories", "notes": "Invitation received"})
        self.assertEqual(updated["application_status"], "interview")
        self.assertEqual(updated["history"][-1]["status"], "interview")
        self.assertEqual(updated["confirmation_reference"], "ABC-123")

    def test_invalid_date_and_status_are_rejected(self) -> None:
        tracker = initial_tracker("lead-1", "Acme", "Analyst", "Received")
        with self.assertRaisesRegex(ValueError, "valid application status"):
            update_tracker(tracker, {"application_status": "maybe"})
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            update_tracker(tracker, {"application_status": "submitted", "follow_up_date": "tomorrow"})


if __name__ == "__main__": unittest.main()

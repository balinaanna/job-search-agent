import unittest

from workflow_api import practice_confirmation_required, revision_instructions


class PracticeOnlyGuardTests(unittest.TestCase):
    def test_requires_explicit_confirmation_for_practice_only_package(self):
        manifest = {"application": {"mode": "practice_only"}}
        self.assertTrue(practice_confirmation_required(manifest, {}))
        self.assertFalse(practice_confirmation_required(manifest, {"practice_only_confirmed": True}))

    def test_active_application_does_not_require_practice_confirmation(self):
        self.assertFalse(practice_confirmation_required({"application": {"mode": "active_application"}}, {}))


class RevisionInstructionsTests(unittest.TestCase):
    def test_builds_revision_request_from_review_findings_without_user_notes(self):
        review = {"findings": [{"location": "Summary", "revision_instruction": "Clarify the opening sentence."}]}
        instructions = revision_instructions(review, "", "resume")
        self.assertIn("Summary: Clarify the opening sentence.", instructions)

    def test_appends_optional_user_direction(self):
        review = {"findings": [{"paragraph_id": "p2", "revision_instruction": "Shorten this paragraph."}]}
        instructions = revision_instructions(review, "Keep the client example.", "cover letter")
        self.assertIn("p2: Shorten this paragraph.", instructions)
        self.assertIn("Additional user direction: Keep the client example.", instructions)

    def test_requires_notes_only_when_review_has_no_revision_instructions(self):
        self.assertEqual(revision_instructions({"findings": []}, "", "resume"), "")


if __name__ == "__main__":
    unittest.main()

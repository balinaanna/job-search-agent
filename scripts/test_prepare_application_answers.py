#!/usr/bin/env python3

import unittest

from prepare_application_answers import apply_answer_review, classify, strategy_for


class ApplicationAnswerPreparationTests(unittest.TestCase):
    def test_commitments_and_sensitive_questions_require_protected_categories(self) -> None:
        cases = {
            "What are your salary expectations?": "salary",
            "Are you willing to relocate?": "relocation",
            "Will you require visa sponsorship?": "work_authorization",
            "Do you consent to a background check?": "legal_declaration",
            "Do you identify as a person with a disability?": "sensitive_personal",
            "When are you available to start?": "start_date",
        }
        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertEqual(classify(question), expected)

    def test_documents_and_narrative_questions_are_distinguished(self) -> None:
        self.assertEqual(classify("Please upload your resume"), "attachment")
        self.assertEqual(classify("Why are you interested in this role?"), "narrative")

    def test_strategy_selection_prefers_question_overlap(self) -> None:
        strategies = [
            {"category": "motivation", "central_message": "Role motivation", "recommended_ids": []},
            {"category": "customer support", "central_message": "Customer support experience", "recommended_ids": ["E-1"]},
        ]
        self.assertEqual(strategy_for("Describe your customer support experience", strategies), strategies[1])

    def test_review_requires_answers_and_never_authorizes_submission(self) -> None:
        plan = {"answers": [{"question_id": "q_001", "question": "Salary?", "status": "requires_user_input", "proposed_answer": None, "reviewed": False}], "submission_authorized": False}
        with self.assertRaisesRegex(ValueError, "Answer required"):
            apply_answer_review(plan, [{"question_id": "q_001", "answer": ""}])
        reviewed = apply_answer_review(plan, [{"question_id": "q_001", "answer": "Prefer to discuss"}])
        self.assertTrue(reviewed["answers_approved"])
        self.assertFalse(reviewed["submission_authorized"])
        self.assertEqual(reviewed["answers"][0]["status"], "user_confirmed")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3

import unittest

from prepare_application_answers import apply_answer_review, classify, strategy_for, validate_form_fill_confirmation, validate_submission_authorization


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

    def test_form_fill_confirmation_requires_every_field_and_documents(self) -> None:
        answers = {"answers": [{"question_id": "q_001"}, {"question_id": "q_002"}]}
        with self.assertRaisesRegex(ValueError, "Confirm every answer"):
            validate_form_fill_confirmation(answers, ["q_001"], True)
        with self.assertRaisesRegex(ValueError, "Confirm every answer"):
            validate_form_fill_confirmation(answers, ["q_001", "q_002"], False)
        self.assertEqual(validate_form_fill_confirmation(answers, ["q_002", "q_001"], True), ["q_001", "q_002"])

    def test_submission_authorization_is_explicit_and_scoped_to_reviewed_form(self) -> None:
        answers = {"answers_approved": True, "submission_authorized": False, "answers": [{"question_id": "q_001"}]}
        session = {"status": "submission_review_required", "completed_question_ids": ["q_001"], "documents_checked": True, "submit_clicked": False}
        confirmations = {"answers_confirmed": True, "documents_confirmed": True, "commitments_confirmed": True, "authorize_now": True, "authorization": "authorize_submission"}
        validate_submission_authorization(confirmations, answers, session)
        with self.assertRaisesRegex(ValueError, "every final-review confirmation"):
            validate_submission_authorization({**confirmations, "commitments_confirmed": False}, answers, session)
        with self.assertRaisesRegex(ValueError, "Explicit submission authorization"):
            validate_submission_authorization({**confirmations, "authorization": "review_only"}, answers, session)


if __name__ == "__main__":
    unittest.main()

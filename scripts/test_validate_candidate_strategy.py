import unittest

from validate_candidate_strategy import career_ids


class CandidateStrategyValidationTests(unittest.TestCase):
    def test_certification_ids_are_profile_ids(self) -> None:
        career = {"training_and_certifications": [{"id": "azure_ai_900"}]}
        self.assertIn("azure_ai_900", career_ids(career))


if __name__ == "__main__":
    unittest.main()

import unittest

from validate_candidate_strategy import career_ids, check_many, nested_ids


class CandidateStrategyValidationTests(unittest.TestCase):
    def test_certification_ids_are_profile_ids(self) -> None:
        career = {"training_and_certifications": [{"id": "azure_ai_900"}]}
        self.assertIn("azure_ai_900", career_ids(career))

    def test_top_skill_ids_accepts_technology_ids(self) -> None:
        # "Python" and similar tools live in technologies.yaml, not skills.yaml, but a
        # strategy's top_skill_ids legitimately cites both (mirrors keyword_strategy's
        # supporting_ids, which already validates against skills + technologies combined).
        skill_ids = nested_ids({"business_analysis": [{"id": "requirements_gathering"}]})
        tech_ids = nested_ids({"programming": [{"id": "python"}]})
        errors: list[str] = []
        check_many(errors, ["python", "requirements_gathering"], skill_ids | tech_ids, "top_skill_ids")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()

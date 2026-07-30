import unittest

from validate_resume_plan import allowed_titles, plan_date, planned_record_id


class ResumePlanCompatibilityTests(unittest.TestCase):
    def test_accepts_structured_approved_title_variants(self):
        role = {"official_title": "AI Solutions Consultant", "approved_title_variants": [{"title": "AI Application Developer", "usage": "Development roles"}]}
        self.assertIn("AI Application Developer", allowed_titles(role))

    def test_reads_current_nested_plan_dates(self):
        entry = {"dates": {"start": "2022-01", "end": "2023-02"}}
        self.assertEqual(plan_date(entry, "start"), "2022-01")
        self.assertEqual(plan_date(entry, "end"), "2023-02")

    def test_reads_current_skill_and_education_ids(self):
        self.assertEqual(planned_record_id({"verified_record_id": "javascript"}), "javascript")
        self.assertEqual(planned_record_id({"education_id": "masters"}, "education_plan"), "masters")

    def test_falls_back_to_plain_id_field(self):
        # Neither record_id, verified_record_id, nor {singular}_id are specified anywhere
        # (the schema leaves education_plan/certification_plan items unstructured), and one
        # generation provider used a plain "id" field instead of the historical conventions.
        self.assertEqual(planned_record_id({"id": "masters_mechanical_engineering"}, "education_plan"), "masters_mechanical_engineering")
        self.assertEqual(planned_record_id({"id": "npower_junior_data_analyst"}, "certification_plan"), "npower_junior_data_analyst")


if __name__ == "__main__":
    unittest.main()

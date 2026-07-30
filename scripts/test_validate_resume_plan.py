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


if __name__ == "__main__":
    unittest.main()

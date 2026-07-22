import unittest

from validate_resume_draft import content_without_certifications
from write_resume_with_codex import normalize_section_headings


class ResumeDraftHelperTests(unittest.TestCase):
    def test_verified_credential_title_is_not_treated_as_keyword_stuffing(self) -> None:
        resume = "## PROFESSIONAL SUMMARY\nAnalyst\n\n## CERTIFICATIONS\nIBM Data Analyst Professional Certificate\n"
        checked = content_without_certifications(resume)
        self.assertNotIn("Data Analyst", checked)
        self.assertIn("Analyst", checked)

    def test_core_skills_heading_is_normalized_to_plan_label(self) -> None:
        self.assertEqual(normalize_section_headings("## CORE SKILLS\nSQL"), "## SKILLS\nSQL")


if __name__ == "__main__":
    unittest.main()

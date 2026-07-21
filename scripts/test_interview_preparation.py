import json
import tempfile
import unittest
from pathlib import Path

from interview_preparation import build_interview_preparation, prepare_for_lead

class InterviewPreparationTests(unittest.TestCase):
    def test_uses_only_selected_verified_story(self):
        lead={"lead_id":"x","identity":{"company":"C"},"position":{"title":"R"},"source":{"collected_at":"now","posting_url":"url"}}
        analysis={"hiring_priorities":[{"priority":"Build"}]}
        choice={"story_id":"s1","question_types":["Conflict"],"why_it_fits":"why","role_emphasis":"focus","keep_concise":"guard"}
        strategy={"interview_strategy":{"selected_stories":[choice],"most_likely_concern":"gap","response_strategy":"honest","verify_before_interview":["fact"],"questions_to_ask":["question"]}}
        library={"stories":[{"id":"s1","evidence_id":"ev1","core_message":"message","star":{"situation":"s"},"lesson":"lesson","best_for":["Tell me"]}]}
        result=build_interview_preparation(lead,analysis,strategy,library)
        self.assertEqual(result["stories"][0]["evidence_id"],"ev1")
        self.assertEqual(result["most_likely_concern"],"gap")

    def test_requires_analysis_before_preparing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            leads = root / "data/job-leads"
            leads.mkdir(parents=True)
            (leads / "x.json").write_text(json.dumps({"lead_id": "x"}))

            with self.assertRaisesRegex(
                ValueError, "Analyze this job before creating interview preparation"
            ):
                prepare_for_lead(root, "x")

if __name__ == "__main__": unittest.main()

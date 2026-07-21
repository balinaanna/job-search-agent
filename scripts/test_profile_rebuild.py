import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from profile_rebuild_store import ProfileRebuildStore
from profile_version import PROFILE_FILES, analysis_profile_version, profile_version
from rebuild_profile_with_codex import apply_profile_rebuild, validate_proposal


class ProfileVersionTests(unittest.TestCase):
    def test_version_changes_when_a_profile_file_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            for name in PROFILE_FILES:
                (profile / name).write_text(f"name: {name}\n", encoding="utf-8")
            before = profile_version(profile)
            (profile / "skills.yaml").write_text("skills: [analysis]\n", encoding="utf-8")
            self.assertNotEqual(before, profile_version(profile))

    def test_analysis_version_is_read_from_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            analysis = Path(directory)
            self.assertIsNone(analysis_profile_version(analysis))
            (analysis / "analysis_metadata.json").write_text(json.dumps({"profile_version": "abc"}))
            self.assertEqual("abc", analysis_profile_version(analysis))


class ProfileProposalValidationTests(unittest.TestCase):
    def proposal(self):
        documents = {
            "career.yaml": {"contact": {"email": "kept@example.com"}, "roles": [{"evidence_ids": ["ev_1"]}]},
            "skills.yaml": {"skills": [{"evidence_ids": ["ev_1"]}]},
            "technologies.yaml": {"technologies": [{"evidence_ids": ["ev_1"]}]},
            "evidence.yaml": {"evidence": [{"id": "ev_1", "claim": "Supported"}]},
        }
        return {name.replace(".yaml", "_yaml"): yaml.safe_dump(value) for name, value in documents.items()}

    def test_accepts_complete_linked_profile_and_preserves_contact(self):
        parsed = validate_proposal(Path("profile"), self.proposal(), {"email": "kept@example.com"})
        self.assertEqual("kept@example.com", parsed["career.yaml"]["contact"]["email"])

    def test_rejects_contact_change(self):
        proposal = self.proposal()
        proposal["career_yaml"] = yaml.safe_dump({"contact": {"email": "changed@example.com"}})
        with self.assertRaisesRegex(ValueError, "protected contact"):
            validate_proposal(Path("profile"), proposal, {"email": "kept@example.com"})

    def test_rejects_unknown_evidence_reference(self):
        proposal = self.proposal()
        proposal["skills_yaml"] = yaml.safe_dump({"skills": [{"evidence_ids": ["missing"]}]})
        with self.assertRaisesRegex(ValueError, "Unknown evidence IDs"):
            validate_proposal(Path("profile"), proposal, {"email": "kept@example.com"})


class ProfileRebuildStoreTests(unittest.TestCase):
    def test_records_rebuild_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProfileRebuildStore(Path(directory) / "runs.db")
            run = store.request(["resume.pdf"], "keep contacts", "before")
            completed = store.update(run["id"], "completed", summary={"changes": []}, after_version="after")
            self.assertEqual("completed", completed["status"])
            self.assertEqual("after", completed["after_version"])
            self.assertEqual(["resume.pdf"], completed["files"])
            store.connection.close()


class ProfileApprovalTests(unittest.TestCase):
    def make_profile(self, root: Path):
        profile = root / "profile"; profile.mkdir()
        for name in PROFILE_FILES:
            (profile / name).write_text(f"state: current-{name}\n", encoding="utf-8")
        proposed = root / "data/profile-rebuilds/run-1"; proposed.mkdir(parents=True)
        for name in PROFILE_FILES:
            (proposed / name).write_text(f"state: proposed-{name}\n", encoding="utf-8")
        return profile

    def test_approval_applies_staged_files_and_keeps_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); profile = self.make_profile(root); before = profile_version(profile)
            with patch("rebuild_profile_with_codex.ROOT", root):
                result = apply_profile_rebuild("run-1", before)
            self.assertEqual("state: proposed-career.yaml\n", (profile / "career.yaml").read_text())
            self.assertEqual("state: current-career.yaml\n", (root / "profile/history/run-1/career.yaml").read_text())
            self.assertEqual(profile_version(profile), result["profile_version"])

    def test_approval_is_blocked_if_current_profile_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); profile = self.make_profile(root); before = profile_version(profile)
            (profile / "skills.yaml").write_text("state: changed-after-proposal\n", encoding="utf-8")
            with patch("rebuild_profile_with_codex.ROOT", root), self.assertRaisesRegex(ValueError, "changed while"):
                apply_profile_rebuild("run-1", before)


if __name__ == "__main__":
    unittest.main()

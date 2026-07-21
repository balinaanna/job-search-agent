import unittest

from workflow_api import practice_confirmation_required


class PracticeOnlyGuardTests(unittest.TestCase):
    def test_requires_explicit_confirmation_for_practice_only_package(self):
        manifest = {"application": {"mode": "practice_only"}}
        self.assertTrue(practice_confirmation_required(manifest, {}))
        self.assertFalse(practice_confirmation_required(manifest, {"practice_only_confirmed": True}))

    def test_active_application_does_not_require_practice_confirmation(self):
        self.assertFalse(practice_confirmation_required({"application": {"mode": "active_application"}}, {}))


if __name__ == "__main__":
    unittest.main()

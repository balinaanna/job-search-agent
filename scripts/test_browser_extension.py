#!/usr/bin/env python3

import io
import json
import tempfile
import unittest
import zipfile
import hashlib
from pathlib import Path

from workflow_api import browser_extension_archive, verified_document_bytes


class BrowserExtensionArchiveTests(unittest.TestCase):
    def test_download_contains_only_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in {
                "manifest.json": '{"version":"0.1.0"}',
                "background.js": "background",
                "form-matcher.js": "matcher",
                "job-capture.js": "capture",
                "content-script.js": "content",
                "README.md": "instructions",
                "test-form-matcher.mjs": "not shipped",
            }.items():
                (root / name).write_text(content, encoding="utf-8")
            body = browser_extension_archive(root)
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            names = sorted(archive.namelist())
            self.assertEqual(names, [
                "job-application-assistant/README.md",
                "job-application-assistant/background.js",
                "job-application-assistant/content-script.js",
                "job-application-assistant/form-matcher.js",
                "job-application-assistant/job-capture.js",
                "job-application-assistant/manifest.json",
            ])
            manifest = json.loads(archive.read("job-application-assistant/manifest.json"))
            self.assertEqual(manifest["version"], "0.1.0")

    def test_document_bytes_must_match_approved_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.pdf"; path.write_bytes(b"approved pdf bytes")
            expected = hashlib.sha256(b"approved pdf bytes").hexdigest()
            self.assertEqual(verified_document_bytes(path, expected), b"approved pdf bytes")
            with self.assertRaisesRegex(ValueError, "integrity check failed"):
                verified_document_bytes(path, "0" * 64)


if __name__ == "__main__":
    unittest.main()

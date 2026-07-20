#!/usr/bin/env python3

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from workflow_api import browser_extension_archive


class BrowserExtensionArchiveTests(unittest.TestCase):
    def test_download_contains_only_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in {
                "manifest.json": '{"version":"0.1.0"}',
                "form-matcher.js": "matcher",
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
                "job-application-assistant/content-script.js",
                "job-application-assistant/form-matcher.js",
                "job-application-assistant/manifest.json",
            ])
            manifest = json.loads(archive.read("job-application-assistant/manifest.json"))
            self.assertEqual(manifest["version"], "0.1.0")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3

import tempfile, unittest
from pathlib import Path
from discovery_store import DiscoveryStore

class DiscoveryStoreTests(unittest.TestCase):
    def setUp(self): self.temp = tempfile.TemporaryDirectory(); self.store = DiscoveryStore(Path(self.temp.name) / "jobs.db")
    def tearDown(self): self.store.connection.close(); self.temp.cleanup()
    def test_request_is_idempotent_while_active(self):
        first = self.store.request(); second = self.store.request(); self.assertEqual(first["id"], second["id"])
    def test_completed_run_records_summary(self):
        run = self.store.request(); self.store.transition(run["id"], "running"); done = self.store.transition(run["id"], "completed", summary={"discovered": 12}); self.assertEqual(done["summary"]["discovered"], 12)
    def test_invalid_transition_is_rejected(self):
        run = self.store.request()
        with self.assertRaisesRegex(ValueError, "Invalid discovery transition"): self.store.transition(run["id"], "completed")
if __name__ == "__main__": unittest.main()

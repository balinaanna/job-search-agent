#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workflow_store import WorkflowStore
from analyze_job_with_codex import strict_output_schema


class WorkflowStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = WorkflowStore(Path(self.temp.name) / "jobs.db")

    def tearDown(self) -> None:
        self.store.connection.close()
        self.temp.cleanup()

    def test_analysis_request_is_idempotent(self) -> None:
        first = self.store.request_analysis("lead-1")
        second = self.store.request_analysis("lead-1")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.store.events(first["id"])), 1)

    def test_valid_analysis_lifecycle_is_audited(self) -> None:
        run = self.store.request_analysis("lead-1")
        self.store.transition(run["id"], "analysis_running", "worker")
        finished = self.store.transition(
            run["id"], "analysis_completed", "worker", result_path="analysis.json"
        )
        self.assertEqual(finished["status"], "analysis_completed")
        self.assertEqual(finished["result_path"], "analysis.json")
        self.assertEqual(len(self.store.events(run["id"])), 3)

    def test_skipping_analysis_is_rejected(self) -> None:
        run = self.store.request_analysis("lead-1")
        with self.assertRaisesRegex(ValueError, "Invalid workflow transition"):
            self.store.transition(run["id"], "pursue", "user")

    def test_submission_state_does_not_exist(self) -> None:
        run = self.store.request_analysis("lead-1")
        with self.assertRaises(ValueError):
            self.store.transition(run["id"], "applied", "user")

    def test_structured_output_schema_requires_every_object_property(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "details": {
                    "type": "object",
                    "properties": {"note": {"type": ["string", "null"]}},
                },
            },
        }
        strict = strict_output_schema(schema)
        self.assertEqual(strict["required"], ["name", "details"])
        self.assertEqual(strict["properties"]["details"]["required"], ["note"])
        self.assertNotIn("required", schema)

    def test_completed_analysis_can_be_imported_for_a_user_decision(self) -> None:
        run = self.store.record_completed_analysis("lead-1", "analysis.json")
        decided = self.store.transition(run["id"], "pursue", "user")
        self.assertEqual(decided["status"], "pursue")
        self.assertEqual(len(self.store.events(run["id"])), 2)

    def test_decide_later_can_change_to_pass(self) -> None:
        run = self.store.record_completed_analysis("lead-1", "analysis.json")
        later = self.store.transition(run["id"], "decide_later", "user")
        decided = self.store.transition(later["id"], "pass", "user")
        self.assertEqual(decided["status"], "pass")

    def test_strategy_requires_pursue_and_completes_in_order(self) -> None:
        run = self.store.record_completed_analysis("lead-1", "analysis.json")
        pursued = self.store.transition(run["id"], "pursue", "user")
        requested = self.store.transition(pursued["id"], "strategy_requested", "user")
        running = self.store.transition(requested["id"], "strategy_running", "worker")
        complete = self.store.transition(
            running["id"], "strategy_completed", "worker", result_path="strategy.json"
        )
        self.assertEqual(complete["status"], "strategy_completed")

    def test_strategy_cannot_start_from_analysis_completed(self) -> None:
        run = self.store.record_completed_analysis("lead-1", "analysis.json")
        with self.assertRaises(ValueError):
            self.store.transition(run["id"], "strategy_requested", "user")

    def test_resume_plan_requires_completed_strategy(self) -> None:
        run = self.store.record_completed_analysis("lead-1", "analysis.json")
        pursued = self.store.transition(run["id"], "pursue", "user")
        requested = self.store.transition(pursued["id"], "strategy_requested", "user")
        running = self.store.transition(requested["id"], "strategy_running", "worker")
        strategy = self.store.transition(running["id"], "strategy_completed", "worker")
        plan_requested = self.store.transition(strategy["id"], "resume_plan_requested", "user")
        plan_running = self.store.transition(plan_requested["id"], "resume_plan_running", "worker")
        plan = self.store.transition(plan_running["id"], "resume_plan_completed", "worker")
        self.assertEqual(plan["status"], "resume_plan_completed")

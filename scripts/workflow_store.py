#!/usr/bin/env python3

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_TRANSITIONS = {
    "analysis_requested": {"analysis_running", "analysis_failed"},
    "analysis_running": {"analysis_completed", "analysis_failed"},
    "analysis_failed": {"analysis_requested"},
    "analysis_completed": {"pursue", "pass", "decide_later"},
    "decide_later": {"pursue", "pass"},
    "pursue": {"strategy_requested"},
    "strategy_requested": {"strategy_running", "strategy_failed"},
    "strategy_running": {"strategy_completed", "strategy_failed"},
    "strategy_failed": {"strategy_requested"},
    "strategy_completed": {"resume_plan_requested"},
    "resume_plan_requested": {"resume_plan_running", "resume_plan_failed"},
    "resume_plan_running": {"resume_plan_completed", "resume_plan_failed"},
    "resume_plan_failed": {"resume_plan_requested"},
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.initialize()

    def initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS workflow_runs (
              id TEXT PRIMARY KEY,
              lead_id TEXT NOT NULL,
              workflow TEXT NOT NULL,
              status TEXT NOT NULL,
              error TEXT,
              result_path TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_analysis_per_lead
              ON workflow_runs(lead_id)
              WHERE workflow = 'job_analysis'
                AND status IN ('analysis_requested', 'analysis_running');
            CREATE TABLE IF NOT EXISTS workflow_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id TEXT NOT NULL REFERENCES workflow_runs(id),
              from_status TEXT,
              to_status TEXT NOT NULL,
              actor TEXT NOT NULL,
              details TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def request_analysis(self, lead_id: str, actor: str = "user") -> dict[str, Any]:
        existing = self.connection.execute(
            """SELECT * FROM workflow_runs WHERE lead_id = ? AND workflow = 'job_analysis'
               AND status IN ('analysis_requested', 'analysis_running')""",
            (lead_id,),
        ).fetchone()
        if existing:
            return dict(existing)
        run_id = str(uuid.uuid4())
        timestamp = now()
        with self.connection:
            self.connection.execute(
                """INSERT INTO workflow_runs
                   (id, lead_id, workflow, status, created_at, updated_at)
                   VALUES (?, ?, 'job_analysis', 'analysis_requested', ?, ?)""",
                (run_id, lead_id, timestamp, timestamp),
            )
            self._event(run_id, None, "analysis_requested", actor, {})
        return self.get(run_id)

    def record_completed_analysis(
        self, lead_id: str, result_path: str, actor: str = "system_import"
    ) -> dict[str, Any]:
        existing = self.latest_for_lead(lead_id)
        if existing and existing["status"] in {
            "analysis_completed",
            "decide_later",
            "pursue",
            "pass",
        }:
            return existing
        run_id = str(uuid.uuid4())
        timestamp = now()
        with self.connection:
            self.connection.execute(
                """INSERT INTO workflow_runs
                   (id, lead_id, workflow, status, result_path, created_at, updated_at)
                   VALUES (?, ?, 'job_analysis', 'analysis_completed', ?, ?, ?)""",
                (run_id, lead_id, result_path, timestamp, timestamp),
            )
            self._event(
                run_id,
                None,
                "analysis_completed",
                actor,
                {"imported_validated_analysis": True},
            )
        return self.get(run_id)

    def transition(
        self,
        run_id: str,
        status: str,
        actor: str,
        details: dict[str, Any] | None = None,
        error: str | None = None,
        result_path: str | None = None,
    ) -> dict[str, Any]:
        run = self.get(run_id)
        current = run["status"]
        if status not in ALLOWED_TRANSITIONS.get(current, set()):
            raise ValueError(f"Invalid workflow transition: {current} -> {status}")
        timestamp = now()
        with self.connection:
            self.connection.execute(
                """UPDATE workflow_runs SET status = ?, error = ?, result_path = ?,
                   updated_at = ? WHERE id = ?""",
                (status, error, result_path or run["result_path"], timestamp, run_id),
            )
            self._event(run_id, current, status, actor, details or {})
        return self.get(run_id)

    def get(self, run_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM workflow_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if not row:
            raise KeyError(run_id)
        return dict(row)

    def latest_for_lead(self, lead_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            """SELECT * FROM workflow_runs WHERE lead_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (lead_id,),
        ).fetchone()
        return dict(row) if row else None

    def events(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM workflow_events WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def _event(
        self,
        run_id: str,
        from_status: str | None,
        to_status: str,
        actor: str,
        details: dict[str, Any],
    ) -> None:
        self.connection.execute(
            """INSERT INTO workflow_events
               (run_id, from_status, to_status, actor, details, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (run_id, from_status, to_status, actor, json.dumps(details), now()),
        )

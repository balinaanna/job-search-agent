#!/usr/bin/env python3

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now() -> str: return datetime.now(timezone.utc).isoformat()


class DiscoveryStore:
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("""CREATE TABLE IF NOT EXISTS discovery_runs (id TEXT PRIMARY KEY, status TEXT NOT NULL, summary TEXT, error TEXT, log_path TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        self.connection.commit()

    def request(self) -> dict:
        active = self.connection.execute("SELECT * FROM discovery_runs WHERE status IN ('requested','running') ORDER BY created_at DESC LIMIT 1").fetchone()
        if active: return self._decode(active)
        run_id = str(uuid.uuid4()); timestamp = now()
        with self.connection: self.connection.execute("INSERT INTO discovery_runs(id,status,created_at,updated_at) VALUES (?, 'requested', ?, ?)", (run_id, timestamp, timestamp))
        return self.get(run_id)

    def transition(self, run_id: str, status: str, *, summary: dict | None = None, error: str | None = None, log_path: str | None = None) -> dict:
        current = self.get(run_id)["status"]
        allowed = {"requested": {"running", "failed"}, "running": {"completed", "failed"}, "failed": {"requested"}}
        if status not in allowed.get(current, set()): raise ValueError(f"Invalid discovery transition: {current} -> {status}")
        with self.connection: self.connection.execute("UPDATE discovery_runs SET status=?, summary=?, error=?, log_path=COALESCE(?,log_path), updated_at=? WHERE id=?", (status, json.dumps(summary) if summary is not None else None, error, log_path, now(), run_id))
        return self.get(run_id)

    def get(self, run_id: str) -> dict:
        row = self.connection.execute("SELECT * FROM discovery_runs WHERE id=?", (run_id,)).fetchone()
        if not row: raise KeyError(run_id)
        return self._decode(row)

    def latest(self) -> dict | None:
        row = self.connection.execute("SELECT * FROM discovery_runs ORDER BY created_at DESC LIMIT 1").fetchone()
        return self._decode(row) if row else None

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict:
        value = dict(row); value["summary"] = json.loads(value["summary"]) if value.get("summary") else None; return value

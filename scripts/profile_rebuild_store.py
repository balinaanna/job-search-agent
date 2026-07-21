from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProfileRebuildStore:
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("""CREATE TABLE IF NOT EXISTS profile_rebuild_runs (
          id TEXT PRIMARY KEY, status TEXT NOT NULL, files TEXT NOT NULL,
          instructions TEXT NOT NULL, summary TEXT, error TEXT,
          before_version TEXT NOT NULL, after_version TEXT,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        self.connection.commit()

    def request(self, files: list[str], instructions: str, before_version: str) -> dict:
        run_id = str(uuid.uuid4()); timestamp = now()
        with self.connection:
            self.connection.execute(
                "INSERT INTO profile_rebuild_runs VALUES (?, 'requested', ?, ?, NULL, NULL, ?, NULL, ?, ?)",
                (run_id, json.dumps(files), instructions, before_version, timestamp, timestamp),
            )
        return self.get(run_id)

    def update(self, run_id: str, status: str, *, summary: dict | None = None, error: str | None = None, after_version: str | None = None) -> dict:
        with self.connection:
            self.connection.execute(
                "UPDATE profile_rebuild_runs SET status=?, summary=?, error=?, after_version=COALESCE(?,after_version), updated_at=? WHERE id=?",
                (status, json.dumps(summary) if summary is not None else None, error, after_version, now(), run_id),
            )
        return self.get(run_id)

    def get(self, run_id: str) -> dict:
        row = self.connection.execute("SELECT * FROM profile_rebuild_runs WHERE id=?", (run_id,)).fetchone()
        if not row: raise KeyError(run_id)
        return self._decode(row)

    def latest(self) -> dict | None:
        row = self.connection.execute("SELECT * FROM profile_rebuild_runs ORDER BY created_at DESC LIMIT 1").fetchone()
        return self._decode(row) if row else None

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict:
        value = dict(row)
        value["files"] = json.loads(value["files"])
        value["summary"] = json.loads(value["summary"]) if value.get("summary") else None
        return value

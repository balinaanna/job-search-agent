#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from workflow_store import WorkflowStore

ROOT = Path(__file__).resolve().parent.parent


def diagnostic_error(exc: subprocess.CalledProcessError | Exception) -> str:
    if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
        stderr = exc.stderr.strip()
        # The Python traceback repeats the entire prompt inside CalledProcessError,
        # obscuring the actual Codex diagnostic that appears immediately before it.
        stderr = stderr.split("Traceback (most recent call last):", 1)[0].strip()
        if len(stderr) > 8000:
            return stderr[-8000:]
        return stderr
    return str(exc)


def revision_notes(store: WorkflowStore, run_id: str) -> str:
    for event in reversed(store.events(run_id)):
        if event["to_status"] == "resume_revision_requested":
            details = json.loads(event["details"])
            notes = str(details.get("notes", "")).strip()
            if notes:
                return notes
    return ""


def main() -> int:
    run_id = sys.argv[1]
    store = WorkflowStore(ROOT / "data/jobs.db")
    run = store.get(run_id)
    notes = revision_notes(store, run_id)
    if not notes:
        store.transition(run_id, "resume_revision_failed", "resume_revision_worker", error="Revision notes were not found.")
        return 1
    if run["status"] == "resume_revision_requested":
        run = store.transition(run_id, "resume_revision_running", "resume_revision_worker")
    try:
        completed = subprocess.run(
            [sys.executable, "scripts/revise_resume_with_codex.py", run["lead_id"], "--notes", notes],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        path = completed.stdout.strip().splitlines()[-1]
        store.transition(
            run_id, "resume_revision_completed", "resume_revision_worker",
            details={"validated": True}, result_path=path,
        )
        return 0
    except (subprocess.CalledProcessError, IndexError) as exc:
        store.transition(
            run_id, "resume_revision_failed", "resume_revision_worker",
            error=diagnostic_error(exc),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

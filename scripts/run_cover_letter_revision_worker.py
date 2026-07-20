#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from workflow_store import WorkflowStore

ROOT = Path(__file__).resolve().parent.parent


def revision_notes(store: WorkflowStore, run_id: str) -> str:
    for event in reversed(store.events(run_id)):
        if event["to_status"] == "cover_letter_revision_requested":
            notes = str(json.loads(event["details"]).get("notes", "")).strip()
            if notes:
                return notes
    return ""


def main() -> int:
    run_id = sys.argv[1]
    store = WorkflowStore(ROOT / "data/jobs.db")
    run = store.transition(run_id, "cover_letter_revision_running", "cover_letter_revision_worker")
    notes = revision_notes(store, run_id)
    if not notes:
        store.transition(run_id, "cover_letter_revision_failed", "cover_letter_revision_worker", error="Revision notes were not found.")
        return 1
    try:
        result = subprocess.run([sys.executable, "scripts/revise_cover_letter_with_codex.py", run["lead_id"], "--notes", notes], cwd=ROOT, check=True, capture_output=True, text=True)
        path = result.stdout.strip().splitlines()[-1]
        store.transition(run_id, "cover_letter_revision_completed", "cover_letter_revision_worker", details={"validated": True}, result_path=path)
        return 0
    except (subprocess.CalledProcessError, IndexError) as exc:
        stderr = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else ""
        store.transition(run_id, "cover_letter_revision_failed", "cover_letter_revision_worker", error=stderr[-4000:] if stderr else str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

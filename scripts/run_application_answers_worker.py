#!/usr/bin/env python3

from __future__ import annotations
import subprocess, sys
from pathlib import Path
from workflow_store import WorkflowStore

ROOT = Path(__file__).resolve().parent.parent
def main() -> int:
    run_id = sys.argv[1]; store = WorkflowStore(ROOT / "data/jobs.db")
    run = store.transition(run_id, "application_answers_running", "application_answers_worker")
    try:
        result = subprocess.run([sys.executable, "scripts/prepare_application_answers.py", run["lead_id"]], cwd=ROOT, check=True, capture_output=True, text=True)
        store.transition(run_id, "application_answers_completed", "application_answers_worker", details={"review_required": True, "submission_authorized": False}, result_path=result.stdout.strip().splitlines()[-1]); return 0
    except (subprocess.CalledProcessError, IndexError) as exc:
        error = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc)
        store.transition(run_id, "application_answers_failed", "application_answers_worker", error=error[-4000:]); return 1
if __name__ == "__main__": raise SystemExit(main())

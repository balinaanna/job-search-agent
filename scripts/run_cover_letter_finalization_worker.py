#!/usr/bin/env python3

from __future__ import annotations
import subprocess, sys
from pathlib import Path
from workflow_store import WorkflowStore

ROOT = Path(__file__).resolve().parent.parent

def main() -> int:
    run_id = sys.argv[1]
    store = WorkflowStore(ROOT / "data/jobs.db")
    run = store.transition(run_id, "cover_letter_finalization_running", "cover_letter_finalization_worker")
    try:
        result = subprocess.run([sys.executable, "scripts/finalize_cover_letter.py", run["lead_id"]], cwd=ROOT, check=True, capture_output=True, text=True)
        store.transition(run_id, "cover_letter_finalization_completed", "cover_letter_finalization_worker", details={"validated": True}, result_path=result.stdout.strip().splitlines()[-1])
        return 0
    except (subprocess.CalledProcessError, IndexError) as exc:
        stderr = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else ""
        store.transition(run_id, "cover_letter_finalization_failed", "cover_letter_finalization_worker", error=stderr[-4000:] if stderr else str(exc))
        return 1

if __name__ == "__main__": raise SystemExit(main())

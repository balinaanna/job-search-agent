#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from build_resume_plan_with_codex import MANIFEST_SCHEMA, PLAN_SCHEMA
from workflow_store import WorkflowStore
from write_resume_with_codex import find_workspace

ROOT = Path(__file__).resolve().parent.parent

def main() -> int:
    run_id = sys.argv[1]
    store = WorkflowStore(ROOT / "data/jobs.db")
    run = store.transition(run_id, "resume_plan_running", "resume_plan_worker")
    try:
        try:
            workspace = find_workspace(run["lead_id"])
            existing_plan = workspace / "resume_plan.json"
            if existing_plan.exists():
                subprocess.run(
                    [sys.executable, "scripts/validate_resume_plan.py", str(workspace),
                     "--resume-schema", str(PLAN_SCHEMA), "--manifest-schema", str(MANIFEST_SCHEMA)],
                    cwd=ROOT, check=True, capture_output=True, text=True,
                )
                store.transition(run_id, "resume_plan_completed", "resume_plan_worker",
                                 details={"validated": True, "recovered_existing_artifact": True}, result_path=str(existing_plan))
                return 0
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
        completed = subprocess.run(
            [sys.executable, "scripts/build_resume_plan_with_codex.py", run["lead_id"]],
            cwd=ROOT, check=True, capture_output=True, text=True, timeout=900,
        )
        path = completed.stdout.strip().splitlines()[-1]
        store.transition(run_id, "resume_plan_completed", "resume_plan_worker",
                         details={"validated": True}, result_path=path)
        return 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, IndexError, OSError) as exc:
        stderr = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else ""
        stdout = exc.stdout.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stdout else ""
        detail = stderr or stdout or ("Resume planning timed out after 15 minutes." if isinstance(exc, subprocess.TimeoutExpired) else str(exc))
        store.transition(run_id, "resume_plan_failed", "resume_plan_worker",
                         error=detail[-4000:])
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

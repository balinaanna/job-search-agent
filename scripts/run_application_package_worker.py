#!/usr/bin/env python3

from __future__ import annotations
import subprocess, sys
from pathlib import Path
from run_resume_pdf_worker import pdf_environment, pdf_python
from workflow_store import WorkflowStore

ROOT = Path(__file__).resolve().parent.parent
def main() -> int:
    run_id = sys.argv[1]; store = WorkflowStore(ROOT / "data/jobs.db")
    run = store.transition(run_id, "application_package_running", "application_package_worker")
    try:
        result = subprocess.run([pdf_python(), "scripts/assemble_application_package.py", run["lead_id"]], cwd=ROOT, env=pdf_environment(), check=True, capture_output=True, text=True)
        store.transition(run_id, "application_package_completed", "application_package_worker", details={"validated": True, "submitted": False}, result_path=result.stdout.strip().splitlines()[-1]); return 0
    except (subprocess.CalledProcessError, IndexError) as exc:
        stderr = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else ""
        store.transition(run_id, "application_package_failed", "application_package_worker", error=stderr[-4000:] if stderr else str(exc)); return 1
if __name__ == "__main__": raise SystemExit(main())

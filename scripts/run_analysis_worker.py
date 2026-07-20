#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from workflow_store import WorkflowStore


ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    run_id = sys.argv[1]
    store = WorkflowStore(ROOT / "data/jobs.db")
    run = store.transition(run_id, "analysis_running", "analysis_worker")
    lead_id = run["lead_id"]
    configured = os.environ.get("JOB_ANALYSIS_COMMAND")
    command = (
        shlex.split(configured)
        if configured
        else [sys.executable, "scripts/analyze_job_with_codex.py"]
    )
    try:
        completed = subprocess.run(
            [*command, lead_id], cwd=ROOT, check=True, capture_output=True, text=True
        )
        result_path = completed.stdout.strip().splitlines()[-1]
        subprocess.run(
            [sys.executable, "scripts/validate_job_analysis.py", result_path],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        lead_path = ROOT / "data/job-leads" / f"{lead_id}.json"
        lead = json.loads(lead_path.read_text(encoding="utf-8"))
        lead["status"]["lead_status"] = "analysis_completed"
        lead["status"]["reviewed"] = True
        lead_path.write_text(json.dumps(lead, indent=2) + "\n", encoding="utf-8")
        subprocess.run(
            [sys.executable, "scripts/export_dashboard_data.py"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        store.transition(
            run_id,
            "analysis_completed",
            "analysis_worker",
            details={"validated": True},
            result_path=result_path,
        )
        return 0
    except (subprocess.CalledProcessError, IndexError) as exc:
        store.transition(run_id, "analysis_failed", "analysis_worker", error=str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

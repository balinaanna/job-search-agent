#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from workflow_store import WorkflowStore
from profile_version import profile_version, analysis_profile_version


ROOT = Path(__file__).resolve().parent.parent
PROVIDER_FILE = ROOT / "data/analysis_provider.txt"
PROVIDER_COMMANDS = {
    "codex": [sys.executable, "scripts/analyze_job_with_codex.py"],
    "claude": [sys.executable, "scripts/analyze_job_with_claude.py"],
}


def resolve_command() -> list[str]:
    configured = os.environ.get("JOB_ANALYSIS_COMMAND")
    if configured:
        return shlex.split(configured)
    provider = os.environ.get("JOB_ANALYSIS_PROVIDER")
    if not provider and PROVIDER_FILE.exists():
        provider = PROVIDER_FILE.read_text(encoding="utf-8").strip()
    return PROVIDER_COMMANDS.get((provider or "codex").strip().lower(), PROVIDER_COMMANDS["codex"])


def finalize_analysis(
    store: WorkflowStore, run_id: str, lead_id: str, result_path: str
) -> None:
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
    result_directory = Path(result_path).parent
    (result_directory / "analysis_metadata.json").write_text(json.dumps({
        "profile_version": profile_version(ROOT / "profile"),
        "analysis_run_id": run_id,
    }, indent=2) + "\n", encoding="utf-8")
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


def main() -> int:
    run_id = sys.argv[1]
    store = WorkflowStore(ROOT / "data/jobs.db")
    run = store.transition(run_id, "analysis_running", "analysis_worker")
    lead_id = run["lead_id"]
    existing_result = ROOT / "jobs/analyzed" / lead_id / "analysis.json"
    if existing_result.exists() and analysis_profile_version(existing_result.parent) == profile_version(ROOT / "profile"):
        try:
            finalize_analysis(store, run_id, lead_id, str(existing_result))
            return 0
        except subprocess.CalledProcessError:
            pass
    command = resolve_command()
    try:
        completed = subprocess.run(
            [*command, lead_id], cwd=ROOT, check=True, capture_output=True, text=True
        )
        result_path = completed.stdout.strip().splitlines()[-1]
        finalize_analysis(store, run_id, lead_id, result_path)
        return 0
    except (subprocess.CalledProcessError, IndexError) as exc:
        stderr = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else ""
        error = stderr[-4000:] if stderr else str(exc)
        store.transition(run_id, "analysis_failed", "analysis_worker", error=error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

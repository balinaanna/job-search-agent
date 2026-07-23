#!/usr/bin/env python3

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from workflow_store import WorkflowStore


ROOT = Path(__file__).resolve().parent.parent
PROVIDER_FILE = ROOT / "data/analysis_provider.txt"
PROVIDER_SCRIPTS = {
    "codex": "scripts/build_strategy_with_codex.py",
    "claude": "scripts/build_strategy_with_claude.py",
}


def resolve_script() -> str:
    provider = os.environ.get("JOB_ANALYSIS_PROVIDER")
    if not provider and PROVIDER_FILE.exists():
        provider = PROVIDER_FILE.read_text(encoding="utf-8").strip()
    return PROVIDER_SCRIPTS.get((provider or "codex").strip().lower(), PROVIDER_SCRIPTS["codex"])


def main() -> int:
    run_id = sys.argv[1]
    store = WorkflowStore(ROOT / "data/jobs.db")
    run = store.transition(run_id, "strategy_running", "strategy_worker")
    try:
        completed = subprocess.run(
            [sys.executable, resolve_script(), run["lead_id"]],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        path = completed.stdout.strip().splitlines()[-1]
        store.transition(run_id, "strategy_completed", "strategy_worker",
                         details={"validated": True}, result_path=path)
        return 0
    except (subprocess.CalledProcessError, IndexError) as exc:
        stderr = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else ""
        store.transition(run_id, "strategy_failed", "strategy_worker",
                         error=stderr[-4000:] if stderr else str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

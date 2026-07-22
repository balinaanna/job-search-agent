#!/usr/bin/env python3

from __future__ import annotations

import fcntl
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from job_alert_inbox import AlertInboxStore
from safe_capture_enrichment import enrich_alert_posting
from surface_fit_queue import load_leads


ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    lock_path = ROOT / "data/safe-capture.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        store = AlertInboxStore(ROOT / "data/jobs.db")
        while job := store.claim_safe_capture():
            try:
                posting = enrich_alert_posting(job, ROOT / "strategy/job_sources.json", ROOT / "data/raw-job-postings", datetime.now(timezone.utc).isoformat())
                subprocess.run([sys.executable, "scripts/run_job_discovery.py", "--skip-collection"], cwd=ROOT, check=True, capture_output=True, text=True)
                subprocess.run([sys.executable, "scripts/export_dashboard_data.py"], cwd=ROOT, check=True, capture_output=True, text=True)
                lead = next((item for item in load_leads(ROOT / "data/job-leads") if item["source"]["posting_url"] == posting["posting_url"]), None)
                if not lead:
                    raise ValueError("The safely captured posting could not be linked to its job record.")
                store.mark_captured(job["source"], job["posting_url"], lead["lead_id"])
            except Exception as exc:
                output = ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
                store.mark_safe_capture_failed(job["id"], output or "Safe capture failed.")
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

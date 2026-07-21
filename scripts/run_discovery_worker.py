#!/usr/bin/env python3

from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from discovery_store import DiscoveryStore

ROOT = Path(__file__).resolve().parent.parent
def main() -> int:
    run_id = sys.argv[1]; store = DiscoveryStore(ROOT / "data/jobs.db"); log_path = ROOT / "logs" / f"discovery-{run_id}.log"; log_path.parent.mkdir(parents=True, exist_ok=True)
    store.transition(run_id, "running", log_path=str(log_path.relative_to(ROOT)))
    try:
        discovery = subprocess.run([sys.executable, "scripts/run_job_discovery.py"], cwd=ROOT, check=True, capture_output=True, text=True)
        dashboard = subprocess.run([sys.executable, "scripts/export_dashboard_data.py"], cwd=ROOT, check=True, capture_output=True, text=True)
        data = json.loads((ROOT / "ui/app/dashboard-data.json").read_text(encoding="utf-8")); summary = {**data["summary"], "generatedAt": data["generatedAt"]}
        report_path = ROOT / "data/discovery-source-report.json"
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {"sources": []}
        summary["sourceResults"] = report["sources"]
        summary["partialFailure"] = any(source["status"] == "failed" for source in report["sources"])
        log_path.write_text(discovery.stdout + dashboard.stdout, encoding="utf-8")
        store.transition(run_id, "completed", summary=summary); return 0
    except (subprocess.CalledProcessError, OSError, json.JSONDecodeError) as exc:
        output = ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        log_path.write_text(output + "\n", encoding="utf-8"); store.transition(run_id, "failed", error=output[-4000:] or str(exc)); return 1
if __name__ == "__main__": raise SystemExit(main())

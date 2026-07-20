#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from validate_job_lead import load_json
from workflow_store import WorkflowStore


ROOT = Path(__file__).resolve().parent.parent


class WorkflowHandler(BaseHTTPRequestHandler):
    store: WorkflowStore
    leads_directory: Path

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "http://localhost:3000")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["api", "runs"]:
            try:
                run = self.store.get(parts[2])
                run["events"] = self.store.events(parts[2])
                self.respond(200, run)
            except KeyError:
                self.respond(404, {"error": "Workflow run not found."})
            return
        self.respond(404, {"error": "Not found."})

    def do_POST(self) -> None:
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "analyze":
            self.request_analysis(parts[2])
            return
        self.respond(404, {"error": "Not found."})

    def request_analysis(self, lead_id: str) -> None:
        lead_path = self.leads_directory / f"{lead_id}.json"
        if not lead_path.exists():
            self.respond(404, {"error": "Job lead not found."})
            return
        lead = load_json(lead_path)
        if lead["status"]["lead_status"] in {"archived", "rejected", "closed", "applied"}:
            self.respond(409, {"error": "This job cannot enter analysis from its current state."})
            return
        run = self.store.request_analysis(lead_id)
        if lead["status"]["lead_status"] != "analysis_started":
            lead["status"]["lead_status"] = "analysis_started"
            lead_path.write_text(json.dumps(lead, indent=2) + "\n", encoding="utf-8")
        subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/run_analysis_worker.py"), run["id"]],
            cwd=ROOT,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.respond(202, run)

    def respond(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local workflow API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--database", type=Path, default=ROOT / "data/jobs.db")
    parser.add_argument("--leads", type=Path, default=ROOT / "data/job-leads")
    args = parser.parse_args()
    WorkflowHandler.store = WorkflowStore(args.database)
    WorkflowHandler.leads_directory = args.leads
    server = HTTPServer((args.host, args.port), WorkflowHandler)
    print(f"Workflow API: http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

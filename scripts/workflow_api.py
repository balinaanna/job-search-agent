#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import secrets
import io
import zipfile
import hashlib
import sqlite3
import imaplib
import subprocess
import sys
import threading
import time
import yaml
import re
from email import policy
from email.parser import BytesParser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from write_resume_with_codex import find_workspace
from prepare_application_answers import append_recovery_questions, apply_answer_review, validate_form_fill_confirmation, validate_submission_authorization, validate_submission_result
from run_resume_pdf_worker import PDF_SCHEMA, pdf_environment, pdf_python
from surface_fit_queue import join_results, load_leads, load_valid_analyses
from validate_job_lead import load_json
from workflow_store import WorkflowStore
from application_tracker import initial_tracker, update_tracker
from discovery_store import DiscoveryStore
from search_settings import load_search_settings, save_search_settings
from job_alert_inbox import AlertInboxStore, canonical_job_url, save_captured_posting
from interview_preparation import prepare_for_lead
from build_strategy_with_codex import find_analysis
from export_dashboard_data import build_dashboard_data
from gmail_alerts import keyring_set, load_config as load_gmail_config, poll_gmail, save_config as save_gmail_config
from profile_rebuild_store import ProfileRebuildStore
from profile_version import profile_version, analysis_profile_version


ROOT = Path(__file__).resolve().parent.parent


def enrich_jobs_with_workflow(data: dict, store: WorkflowStore) -> dict:
    current_profile = profile_version(ROOT / "profile")
    for group, fallback in (("analyzedJobs", "analysis_completed"), ("awaitingAnalysis", "not_started")):
        for job in data[group]:
            run = store.latest_for_lead(job["id"])
            job["workflowStatus"] = run["status"] if run else fallback
            job["workflowUpdatedAt"] = run["updated_at"] if run else None
            analyzed_version = None
            if group == "analyzedJobs":
                try: analyzed_version = analysis_profile_version(find_analysis(job["id"]).parent)
                except FileNotFoundError: pass
            job["profileVersion"] = current_profile
            job["analysisProfileVersion"] = analyzed_version
            job["profileStale"] = group == "analyzedJobs" and analyzed_version != current_profile
    return data


def practice_confirmation_required(plan: dict, payload: dict) -> bool:
    return plan.get("application", {}).get("mode") == "practice_only" and payload.get("practice_only_confirmed") is not True


def archived_posting(lead: dict) -> dict:
    return {
        "lead_id": lead["lead_id"], "company": lead["identity"]["company"], "title": lead["position"]["title"],
        "description": lead["content"]["description_text"], "location": lead["location"]["raw"],
        "workplace_type": lead["location"]["workplace_type"], "employment_type": lead["employment"]["employment_type"],
        "salary": lead["employment"]["salary"], "posted_date": lead["application"].get("posted_date"),
        "captured_at": lead["source"]["collected_at"], "source": lead["source"]["platform"],
        "original_url": lead["source"]["posting_url"], "description_hash": lead["content"]["description_hash"],
    }


def scheduled_discovery_loop(database: Path) -> None:
    store = DiscoveryStore(database)
    while True:
        try:
            schedule_path = ROOT / "strategy/discovery_schedule.json"
            frequency = json.loads(schedule_path.read_text(encoding="utf-8")).get("frequency", "manual") if schedule_path.exists() else "manual"
            interval = {"daily": 86400, "weekly": 604800}.get(frequency)
            latest = store.latest()
            last_time = datetime.fromisoformat(latest["created_at"]) if latest else None
            due = interval is not None and (last_time is None or (datetime.now(timezone.utc) - last_time).total_seconds() >= interval)
            if due:
                run = store.request()
                if run["status"] == "requested":
                    subprocess.Popen([sys.executable, str(ROOT / "scripts/run_discovery_worker.py"), run["id"]], cwd=ROOT, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        time.sleep(60)


def gmail_alert_loop(database: Path) -> None:
    store = AlertInboxStore(database); config_path = ROOT / "data/gmail-alerts.json"
    while True:
        wait_seconds = 600
        try:
            config = load_gmail_config(config_path); wait_seconds = int(config.get("poll_minutes", 10)) * 60
            if config.get("connected"): poll_gmail(config, store)
        except (OSError, ValueError, imaplib.IMAP4.error, json.JSONDecodeError):
            pass
        time.sleep(wait_seconds)


def browser_extension_archive(extension: Path = ROOT / "browser-extension") -> bytes:
    files = ("manifest.json", "background.js", "form-matcher.js", "job-capture.js", "content-script.js", "README.md")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(extension / name, f"job-application-assistant/{name}")
    return buffer.getvalue()


def verified_document_bytes(path: Path, expected_sha256: str) -> bytes:
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != expected_sha256:
        raise ValueError("Approved document integrity check failed.")
    return body


class WorkflowHandler(BaseHTTPRequestHandler):
    store: WorkflowStore
    discovery_store: DiscoveryStore
    leads_directory: Path
    alert_store: AlertInboxStore
    profile_store: ProfileRebuildStore

    def end_headers(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin == "http://localhost:3000" or origin.startswith("chrome-extension://"):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Expose-Headers", "X-Content-SHA256, Content-Disposition")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if self.headers.get("Access-Control-Request-Private-Network") == "true":
            self.send_header("Access-Control-Allow-Private-Network", "true")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path); parts = parsed.path.strip("/").split("/")
        if parts == ["api", "jobs"]:
            self.get_jobs_workspace()
            return
        if parts == ["api", "profile"]:
            self.get_profile_status()
            return
        if len(parts) == 4 and parts[:3] == ["api", "profile", "runs"]:
            try: self.respond(200, self.profile_store.get(parts[3]))
            except KeyError: self.respond(404, {"error": "Profile rebuild was not found."})
            return
        if len(parts) == 3 and parts[:2] == ["api", "runs"]:
            try:
                run = self.store.get(parts[2])
                run["events"] = self.store.events(parts[2])
                self.respond(200, run)
            except KeyError:
                self.respond(404, {"error": "Workflow run not found."})
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "workflow":
            run = self.store.latest_for_lead(parts[2])
            self.respond(200, run or {"status": "not_started"})
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "resume-review":
            self.get_resume_review(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "resume-pdf":
            self.get_resume_pdf(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cover-letter-plan":
            self.get_cover_letter_plan(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cover-letter-review":
            self.get_cover_letter_review(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cover-letter-pdf":
            self.get_cover_letter_pdf(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "application-package":
            self.get_application_package(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "application-answers":
            self.get_application_answers(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "browser-fill":
            self.get_browser_fill(parts[2], parsed.query)
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "browser-document":
            self.get_browser_document(parts[2], parsed.query)
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "form-fill-session":
            self.get_form_fill_session(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "application-tracker":
            self.get_application_tracker(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "application-context":
            self.get_application_context(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "job-posting":
            self.get_archived_posting(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "interview-preparation":
            self.get_interview_preparation(parts[2])
            return
        if parts == ["api", "browser-extension"]:
            self.get_browser_extension()
            return
        if parts == ["api", "discovery", "latest"]:
            self.respond(200, self.discovery_store.latest() or {"status": "not_started"})
            return
        if parts == ["api", "search-settings"]:
            try:
                self.respond(200, load_search_settings(ROOT / "strategy/job_search_criteria.json", ROOT / "strategy/job_sources.json", ROOT / "strategy/discovery_schedule.json"))
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                self.respond(500, {"error": str(exc)})
            return
        if parts == ["api", "job-alerts"]:
            jobs = self.alert_store.list()
            leads_by_url = {}
            for lead in load_leads(self.leads_directory):
                source = lead["source"].get("platform")
                posting_url = lead["source"]["posting_url"]
                leads_by_url[(source, canonical_job_url(posting_url, source) or posting_url)] = lead["lead_id"]
            for job in jobs:
                canonical = canonical_job_url(job["posting_url"], job["source"]) or job["posting_url"]
                linked_lead = leads_by_url.get((job["source"], canonical))
                if not job.get("lead_id") and linked_lead:
                    self.alert_store.mark_captured(job["source"], job["posting_url"], linked_lead); job["status"] = "captured"; job["lead_id"] = linked_lead
                run = self.store.latest_for_lead(job["lead_id"]) if job.get("lead_id") else None
                job["workflow_status"] = run["status"] if run else "not_started"
            self.respond(200, {"jobs": jobs})
            return
        if parts == ["api", "gmail-alerts"]:
            self.respond(200, load_gmail_config(ROOT / "data/gmail-alerts.json"))
            return
        self.respond(404, {"error": "Not found."})

    def do_POST(self) -> None:
        parts = urlparse(self.path).path.strip("/").split("/")
        if parts == ["api", "discovery"]:
            self.request_discovery()
            return
        if parts == ["api", "profile", "rebuild"]:
            self.request_profile_rebuild()
            return
        if len(parts) == 5 and parts[:3] == ["api", "profile", "runs"] and parts[4] in {"approve", "reject"}:
            self.review_profile_rebuild(parts[3], parts[4])
            return
        if parts == ["api", "search-settings"]:
            self.update_search_settings()
            return
        if parts == ["api", "job-alerts", "import"]:
            self.import_job_alert()
            return
        if parts == ["api", "job-alerts", "capture"]:
            self.capture_alert_job()
            return
        if parts == ["api", "gmail-alerts", "connect"]:
            self.connect_gmail_alerts()
            return
        if parts == ["api", "gmail-alerts", "check"]:
            self.check_gmail_alerts()
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "analyze":
            self.request_analysis(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "decision":
            self.record_decision(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "strategy":
            self.request_strategy(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "resume-plan":
            self.request_resume_plan(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "resume-draft":
            self.request_resume_draft(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "interview-preparation":
            self.prepare_interview(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "resume-review":
            self.request_resume_review(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "resume-decision":
            self.record_resume_decision(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "resume-revision":
            self.request_resume_revision(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "resume-finalize":
            self.request_resume_finalization(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "resume-pdf":
            self.request_resume_pdf(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "resume-pdf-decision":
            self.record_resume_pdf_decision(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cover-letter-plan":
            self.request_cover_letter_plan(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cover-letter-draft":
            self.request_cover_letter_draft(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cover-letter-review":
            self.request_cover_letter_review(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cover-letter-decision":
            self.record_cover_letter_decision(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cover-letter-revision":
            self.request_cover_letter_revision(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cover-letter-finalize":
            self.request_cover_letter_finalization(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cover-letter-pdf":
            self.request_cover_letter_pdf(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cover-letter-pdf-decision":
            self.record_cover_letter_pdf_decision(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "application-package":
            self.request_application_package(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "form-questions":
            self.save_form_questions(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "application-answers":
            self.request_application_answers(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "application-answers-decision":
            self.approve_application_answers(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "form-fill":
            self.start_form_fill(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "form-fill-ready":
            self.complete_form_fill(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "submission-authorization":
            self.authorize_submission(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "submission-execution":
            self.start_submission(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "submission-result":
            self.record_submission_result(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "submission-recovery":
            self.recover_blocked_submission(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "application-tracker":
            self.update_application_tracker(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "browser-fill-report":
            self.record_browser_fill_report(parts[2])
            return
        self.respond(404, {"error": "Not found."})

    def get_resume_review(self, lead_id: str) -> None:
        try:
            workspace = find_workspace(lead_id)
            review = load_json(workspace / "resume_review.json")
            trace = load_json(workspace / "resume_trace.json")
            resume = (workspace / "resume.md").read_text(encoding="utf-8")
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            self.respond(404, {"error": str(exc)})
            return
        self.respond(200, {"resume": resume, "review": review, "trace": trace})

    def get_resume_pdf(self, lead_id: str) -> None:
        try:
            path = find_workspace(lead_id) / "final_resume.pdf"
            body = path.read_bytes()
        except OSError as exc:
            self.respond(404, {"error": str(exc)})
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", 'inline; filename="final_resume.pdf"')
        self.end_headers()
        self.wfile.write(body)

    def get_cover_letter_plan(self, lead_id: str) -> None:
        try:
            plan = load_json(find_workspace(lead_id) / "cover_letter_plan.json")
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            self.respond(404, {"error": str(exc)})
            return
        self.respond(200, plan)

    def get_cover_letter_review(self, lead_id: str) -> None:
        try:
            workspace = find_workspace(lead_id)
            review = load_json(workspace / "cover_letter_review.json")
            trace = load_json(workspace / "cover_letter_trace.json")
            letter = (workspace / "cover_letter.md").read_text(encoding="utf-8")
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
            self.respond(404, {"error": str(exc)})
            return
        self.respond(200, {"letter": letter, "review": review, "trace": trace})

    def get_cover_letter_pdf(self, lead_id: str) -> None:
        try:
            body = (find_workspace(lead_id) / "final_cover_letter.pdf").read_bytes()
        except OSError as exc:
            self.respond(404, {"error": str(exc)})
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", 'inline; filename="final_cover_letter.pdf"')
        self.end_headers()
        self.wfile.write(body)

    def get_application_package(self, lead_id: str) -> None:
        try:
            workspace = find_workspace(lead_id)
            package = load_json(workspace / "submission/application_package.json")
            checklist = (workspace / "submission/submission_checklist.md").read_text(encoding="utf-8")
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
            self.respond(404, {"error": str(exc)}); return
        self.respond(200, {"package": package, "checklist": checklist})

    def get_application_answers(self, lead_id: str) -> None:
        try:
            self.respond(200, load_json(find_workspace(lead_id) / "application_answers.json"))
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            self.respond(404, {"error": str(exc)})

    def get_form_fill_session(self, lead_id: str) -> None:
        try:
            session = load_json(find_workspace(lead_id) / "form_fill_session.json")
            session.pop("browser_token", None)
            self.respond(200, session)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            self.respond(404, {"error": str(exc)})

    def get_application_tracker(self, lead_id: str) -> None:
        try:
            workspace = find_workspace(lead_id); path = workspace / "application_tracker.json"
            if not path.exists():
                run = self.store.latest_for_lead(lead_id)
                if run is None or run["status"] != "application_submitted": raise FileNotFoundError("A confirmed submission is required before tracking.")
                manifest = load_json(workspace / "application_manifest.json"); session = load_json(workspace / "form_fill_session.json")
                tracker = initial_tracker(lead_id, manifest["company"], manifest["role"], session.get("confirmation_evidence", "Employer confirmation recorded.")); path.write_text(json.dumps(tracker, indent=2) + "\n", encoding="utf-8")
            self.respond(200, load_json(path))
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc: self.respond(404, {"error": str(exc)})

    def update_application_tracker(self, lead_id: str) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError): self.respond(400, {"error": "Invalid tracker update."}); return
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] != "application_submitted": self.respond(409, {"error": "A confirmed submission is required before tracking."}); return
        try:
            path = find_workspace(lead_id) / "application_tracker.json"; tracker = update_tracker(load_json(path), payload); path.write_text(json.dumps(tracker, indent=2) + "\n", encoding="utf-8")
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc: self.respond(409, {"error": str(exc)}); return
        self.respond(200, tracker)

    def get_browser_extension(self) -> None:
        try:
            body = browser_extension_archive()
        except OSError as exc:
            self.respond(500, {"error": str(exc)}); return
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", 'attachment; filename="job-application-assistant.zip"')
        self.end_headers(); self.wfile.write(body)

    def request_discovery(self) -> None:
        run = self.discovery_store.request()
        if run["status"] == "requested": subprocess.Popen([sys.executable, str(ROOT / "scripts/run_discovery_worker.py"), run["id"]], cwd=ROOT, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.respond(202, run)

    def update_search_settings(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("Search settings must be an object.")
            settings = save_search_settings(payload, ROOT / "strategy/job_search_criteria.json", ROOT / "strategy/job_sources.json", ROOT / "strategy/discovery_schedule.json")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            self.respond(400, {"error": str(exc)})
            return
        self.respond(200, settings)

    def import_job_alert(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            result = self.alert_store.import_alert(payload.get("source", ""), payload.get("content", ""))
        except (ValueError, json.JSONDecodeError, sqlite3.Error) as exc:
            self.respond(400, {"error": str(exc)})
            return
        self.respond(200, result)

    def capture_alert_job(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
            path = save_captured_posting(payload, ROOT / "data/raw-job-postings")
            pipeline = subprocess.run([sys.executable, "scripts/run_job_discovery.py", "--skip-collection"], cwd=ROOT, check=True, capture_output=True, text=True)
            subprocess.run([sys.executable, "scripts/export_dashboard_data.py"], cwd=ROOT, check=True, capture_output=True, text=True)
            captured_url = json.loads(path.read_text(encoding="utf-8"))["posting_url"]
            lead = next((item for item in load_leads(ROOT / "data/job-leads") if item["source"]["posting_url"] == captured_url), None)
            if not lead: raise ValueError("The captured posting was processed but its job record could not be linked.")
            self.alert_store.mark_captured(payload["source"], captured_url, lead["lead_id"])
        except (ValueError, KeyError, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
            detail = ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
            self.respond(400, {"error": detail[-2000:] or "Captured posting could not be processed."}); return
        self.respond(201, {"status": "captured", "raw_path": str(path.relative_to(ROOT)), "pipeline": pipeline.stdout.strip()})

    def connect_gmail_alerts(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
            email = payload.get("email", ""); password = payload.get("app_password", ""); interval = int(payload.get("poll_minutes", 10))
            if len(password.replace(" ", "")) != 16: raise ValueError("Enter the 16-character Gmail app password, not your Google password.")
            normalized_email = email.strip().casefold(); keyring_set(normalized_email, password)
            candidate = {"connected": True, "email": normalized_email, "poll_minutes": interval}; result = poll_gmail(candidate, self.alert_store)
            config = save_gmail_config(ROOT / "data/gmail-alerts.json", email, interval)
        except (OSError, ValueError, TypeError, json.JSONDecodeError, imaplib.IMAP4.error) as exc:
            self.respond(400, {"error": str(exc)}); return
        self.respond(200, {**config, "result": result})

    def check_gmail_alerts(self) -> None:
        try:
            config = load_gmail_config(ROOT / "data/gmail-alerts.json")
            if not config["connected"]: raise ValueError("Connect Gmail first.")
            result = poll_gmail(config, self.alert_store)
        except (OSError, ValueError, json.JSONDecodeError, imaplib.IMAP4.error) as exc:
            self.respond(400, {"error": str(exc)}); return
        self.respond(200, result)

    def get_browser_fill(self, lead_id: str, query: str) -> None:
        from urllib.parse import parse_qs
        token = parse_qs(query).get("token", [""])[0]
        try:
            workspace = find_workspace(lead_id); session = load_json(workspace / "form_fill_session.json"); answers = load_json(workspace / "application_answers.json"); package = load_json(workspace / "submission/application_package.json")
            if not token or not secrets.compare_digest(token, session.get("browser_token", "")):
                raise ValueError("Invalid browser-fill token.")
            if session.get("status") != "form_filling_started" or not answers.get("answers_approved"):
                raise ValueError("This browser-fill session is not active.")
            safe_answers = [{"question_id": item["question_id"], "question": item["question"], "answer": item.get("proposed_answer"), "category": item["category"]} for item in answers.get("answers", []) if item.get("proposed_answer")]
            documents = None
            if session.get("document_upload_authorized") is True:
                documents = {"resume": {"filename": "resume.pdf", "sha256": package["hashes"]["packaged_resume_sha256"]}, "cover_letter": {"filename": "cover_letter.pdf", "sha256": package["hashes"]["packaged_cover_letter_sha256"]} if package["packaged_artifacts"]["cover_letter_pdf"] else None}
            self.respond(200, {"lead_id": lead_id, "answers": safe_answers, "documents": documents, "document_upload_authorized": documents is not None, "never_submit": True})
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            self.respond(403, {"error": str(exc)})

    def get_browser_document(self, lead_id: str, query: str) -> None:
        from urllib.parse import parse_qs
        values = parse_qs(query); token = values.get("token", [""])[0]; kind = values.get("kind", [""])[0]
        try:
            workspace = find_workspace(lead_id); session = load_json(workspace / "form_fill_session.json"); package = load_json(workspace / "submission/application_package.json")
            if not token or not secrets.compare_digest(token, session.get("browser_token", "")) or session.get("status") != "form_filling_started" or session.get("document_upload_authorized") is not True:
                raise ValueError("Document upload is not authorized for this session.")
            if kind == "resume": path = workspace / "submission/resume.pdf"; expected = package["hashes"]["packaged_resume_sha256"]; filename = "resume.pdf"
            elif kind == "cover_letter" and package["packaged_artifacts"]["cover_letter_pdf"]: path = workspace / "submission/cover_letter.pdf"; expected = package["hashes"]["packaged_cover_letter_sha256"]; filename = "cover_letter.pdf"
            else: raise ValueError("Requested approved document is unavailable.")
            body = verified_document_bytes(path, expected)
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
            self.respond(403, {"error": str(exc)}); return
        self.send_response(200); self.send_header("Content-Type", "application/pdf"); self.send_header("Content-Length", str(len(body))); self.send_header("X-Content-SHA256", expected); self.send_header("Content-Disposition", f'attachment; filename="{filename}"'); self.end_headers(); self.wfile.write(body)

    def save_form_questions(self, lead_id: str) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self.respond(400, {"error": "Invalid form-question request."}); return
        text = payload.get("questions_text", ""); source_url = payload.get("source_url", "")
        questions = [line.strip().lstrip("-• ").strip() for line in text.splitlines() if line.strip()]
        if not questions:
            self.respond(400, {"error": "Paste at least one application question, one per line."}); return
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] not in {"application_package_completed", "application_answers_failed"}:
            self.respond(409, {"error": "A validated application package is required before importing questions."}); return
        try:
            workspace = find_workspace(lead_id)
            form = {"schema_version": "1.0", "lead_id": lead_id, "source_url": source_url.strip() or None, "questions": [{"question_id": f"q_{index:03d}", "question": question} for index, question in enumerate(questions, 1)]}
            (workspace / "application_form.json").write_text(json.dumps(form, indent=2) + "\n", encoding="utf-8")
            run = self.store.transition(run["id"], "form_questions_saved", "user", details={"question_count": len(questions)})
        except (OSError, ValueError) as exc:
            self.respond(409, {"error": str(exc)}); return
        self.respond(200, run)

    def request_application_answers(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] != "form_questions_saved":
            self.respond(409, {"error": "Import the application questions before preparing answers."}); return
        try:
            run = self.store.transition(run["id"], "application_answers_requested", "user")
        except ValueError as exc:
            self.respond(409, {"error": str(exc)}); return
        subprocess.Popen([sys.executable, str(ROOT / "scripts/run_application_answers_worker.py"), run["id"]], cwd=ROOT, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.respond(202, run)

    def approve_application_answers(self, lead_id: str) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self.respond(400, {"error": "Invalid answer-review request."}); return
        submitted = payload.get("answers")
        if not isinstance(submitted, list):
            self.respond(400, {"error": "Reviewed answers are required."}); return
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] != "application_answers_completed":
            self.respond(409, {"error": "A completed answer plan is required before approval."}); return
        try:
            workspace = find_workspace(lead_id); plan_path = workspace / "application_answers.json"; plan = load_json(plan_path)
            plan = apply_answer_review(plan, submitted)
            plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            run = self.store.transition(run["id"], "application_answers_approved", "user", details={"explicit_answer_approval": True, "question_count": len(plan["answers"]), "submission_authorized": False})
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
            self.respond(409, {"error": str(exc)}); return
        self.respond(200, run)

    def start_form_fill(self, lead_id: str) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self.respond(400, {"error": "Invalid form-filling request."}); return
        source_url = payload.get("source_url", ""); document_upload_authorized = payload.get("document_upload_authorized") is True
        if not isinstance(source_url, str) or not source_url.strip().startswith(("https://", "http://")):
            self.respond(400, {"error": "Enter the employer's application-page URL."}); return
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] != "application_answers_approved":
            self.respond(409, {"error": "Approved application answers are required before form filling."}); return
        try:
            workspace = find_workspace(lead_id); answer_path = workspace / "application_answers.json"; answers = load_json(answer_path)
            if not answers.get("answers_approved") or answers.get("submission_authorized"):
                raise ValueError("Approved answers with submission disabled are required.")
            answers["source_url"] = source_url.strip(); answer_path.write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")
            browser_token = secrets.token_urlsafe(24)
            separator = "&" if "#" in source_url else "#"
            browser_launch_url = f"{source_url.strip()}{separator}jobAgentLead={lead_id}&jobAgentToken={browser_token}"
            session = {"schema_version": "1.0", "lead_id": lead_id, "source_url": source_url.strip(), "status": "form_filling_started", "completed_question_ids": [], "documents_checked": False, "document_upload_authorized": document_upload_authorized, "submit_clicked": False, "browser_token": browser_token, "browser_fill_report": None}
            (workspace / "form_fill_session.json").write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
            run = self.store.transition(run["id"], "form_filling_started", "user", details={"assisted_mode": True, "document_upload_authorized": document_upload_authorized, "submit_clicked": False})
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
            self.respond(409, {"error": str(exc)}); return
        self.respond(200, {**run, "browser_launch_url": browser_launch_url})

    def record_browser_fill_report(self, lead_id: str) -> None:
        from urllib.parse import parse_qs
        token = parse_qs(urlparse(self.path).query).get("token", [""])[0]
        try:
            length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self.respond(400, {"error": "Invalid browser-fill report."}); return
        try:
            session_path = find_workspace(lead_id) / "form_fill_session.json"; session = load_json(session_path)
            if not token or not secrets.compare_digest(token, session.get("browser_token", "")) or session.get("status") != "form_filling_started":
                raise ValueError("This browser-fill session is not active.")
            filled = payload.get("filled", []); uploaded = payload.get("uploaded", []); unmatched = payload.get("unmatched", []); blockers = payload.get("blockers", [])
            if not all(isinstance(value, list) for value in (filled, uploaded, unmatched, blockers)):
                raise ValueError("Browser-fill report lists are invalid.")
            session["browser_fill_report"] = {"filled": filled[:100], "uploaded": uploaded[:10], "unmatched": unmatched[:100], "blockers": blockers[:100], "submit_clicked": False}
            session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
            self.respond(409, {"error": str(exc)}); return
        self.respond(200, {"recorded": True, "submit_clicked": False})

    def complete_form_fill(self, lead_id: str) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self.respond(400, {"error": "Invalid form-completion request."}); return
        completed = payload.get("completed_question_ids"); documents_checked = payload.get("documents_checked")
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] != "form_filling_started":
            self.respond(409, {"error": "Start assisted form filling before requesting final review."}); return
        try:
            workspace = find_workspace(lead_id); answers = load_json(workspace / "application_answers.json"); session_path = workspace / "form_fill_session.json"; session = load_json(session_path)
            confirmed_ids = validate_form_fill_confirmation(answers, completed, documents_checked)
            session.update({"status": "submission_review_required", "completed_question_ids": confirmed_ids, "documents_checked": True, "submit_clicked": False})
            session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
            run = self.store.transition(run["id"], "submission_review_required", "user", details={"all_fields_confirmed": True, "documents_checked": True, "submit_clicked": False, "submission_authorized": False})
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
            self.respond(409, {"error": str(exc)}); return
        self.respond(200, run)

    def authorize_submission(self, lead_id: str) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self.respond(400, {"error": "Invalid submission-authorization request."}); return
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] != "submission_review_required":
            self.respond(409, {"error": "A completed final review is required before submission authorization."}); return
        try:
            workspace = find_workspace(lead_id); answers_path = workspace / "application_answers.json"; session_path = workspace / "form_fill_session.json"
            answers = load_json(answers_path); session = load_json(session_path)
            validate_submission_authorization(payload, answers, session)
            answers["submission_authorized"] = True; answers_path.write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")
            session.update({"status": "submission_authorized", "submission_authorized": True, "submit_clicked": False})
            session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
            run = self.store.transition(run["id"], "submission_authorized", "user", details={"explicit_submission_authorization": True, "scope": lead_id, "submit_clicked": False})
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
            self.respond(409, {"error": str(exc)}); return
        self.respond(200, run)

    def start_submission(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] != "submission_authorized":
            self.respond(409, {"error": "Explicit authorization for this application is required."}); return
        try:
            workspace = find_workspace(lead_id); session_path = workspace / "form_fill_session.json"; session = load_json(session_path)
            if session.get("status") != "submission_authorized" or session.get("submission_authorized") is not True or session.get("submit_clicked") is not False:
                raise ValueError("The submission authorization is not valid for execution.")
            session["status"] = "submission_in_progress"; session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
            run = self.store.transition(run["id"], "submission_in_progress", "user", details={"explicit_authorization_verified": True, "submit_clicked": False})
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
            self.respond(409, {"error": str(exc)}); return
        self.respond(200, run)

    def record_submission_result(self, lead_id: str) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self.respond(400, {"error": "Invalid submission-result request."}); return
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] != "submission_in_progress":
            self.respond(409, {"error": "An authorized submission session must be in progress."}); return
        try:
            outcome, evidence = validate_submission_result(payload)
            workspace = find_workspace(lead_id); session_path = workspace / "form_fill_session.json"; session = load_json(session_path)
            if session.get("status") != "submission_in_progress" or session.get("submission_authorized") is not True:
                raise ValueError("The authorized submission session is not active.")
            status = "application_submitted" if outcome == "submitted" else "submission_blocked"
            session.update({"status": status, "submit_clicked": outcome == "submitted", "confirmation_evidence": evidence})
            session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
            if outcome == "submitted":
                lead_path = self.leads_directory / f"{lead_id}.json"
                lead = load_json(lead_path); lead["status"]["lead_status"] = "applied"
                lead_path.write_text(json.dumps(lead, indent=2) + "\n", encoding="utf-8")
                manifest_path = workspace / "application_manifest.json"; manifest = load_json(manifest_path); manifest["status"] = "submitted"
                manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                tracker = initial_tracker(lead_id, manifest["company"], manifest["role"], evidence)
                (workspace / "application_tracker.json").write_text(json.dumps(tracker, indent=2) + "\n", encoding="utf-8")
            run = self.store.transition(run["id"], status, "user", details={"outcome": outcome, "confirmation_recorded": True, "submit_clicked": outcome == "submitted"})
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
            self.respond(409, {"error": str(exc)}); return
        self.respond(200, run)

    def recover_blocked_submission(self, lead_id: str) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self.respond(400, {"error": "Invalid recovery request."}); return
        notes = payload.get("resolution_notes", ""); questions_text = payload.get("new_questions_text", "")
        if not isinstance(notes, str) or not notes.strip() or not isinstance(questions_text, str):
            self.respond(400, {"error": "Describe the blocker and any action needed before retrying."}); return
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] != "submission_blocked":
            self.respond(409, {"error": "A blocked submission is required before recovery."}); return
        try:
            workspace = find_workspace(lead_id); form_path = workspace / "application_form.json"; answers_path = workspace / "application_answers.json"; session_path = workspace / "form_fill_session.json"
            form = load_json(form_path); added = append_recovery_questions(form, questions_text); form_path.write_text(json.dumps(form, indent=2) + "\n", encoding="utf-8")
            answers = load_json(answers_path); answers["answers_approved"] = False; answers["submission_authorized"] = False; answers_path.write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")
            session = load_json(session_path); session.update({"status": "recovery_requested", "submission_authorized": False, "document_upload_authorized": False, "browser_token": None, "submit_clicked": False, "recovery_notes": notes.strip()}); session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
            run = self.store.transition(run["id"], "form_questions_saved", "user", details={"submission_authorization_revoked": True, "document_upload_authorization_revoked": True, "new_question_count": len(added), "blocker_preserved": True})
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
            self.respond(409, {"error": str(exc)}); return
        self.respond(200, run)

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

    def request_resume_draft(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] not in {"resume_plan_completed", "resume_draft_failed"}:
            self.respond(409, {"error": "A validated resume plan is required before drafting."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
            plan = load_json(find_workspace(lead_id) / "resume_plan.json")
            if practice_confirmation_required(plan, payload):
                self.respond(409, {"error": "This job is marked do not apply. Confirm practice-only drafting before continuing.", "practice_confirmation_required": True})
                return
            run = self.store.transition(run["id"], "resume_draft_requested", "user", details={"practice_only_confirmed": plan.get("application", {}).get("mode") == "practice_only"})
        except (ValueError, json.JSONDecodeError, FileNotFoundError) as exc:
            self.respond(409, {"error": str(exc)})
            return
        subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/run_resume_draft_worker.py"), run["id"]],
            cwd=ROOT, start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.respond(202, run)

    def get_application_context(self, lead_id: str) -> None:
        try:
            workspace = find_workspace(lead_id); manifest = load_json(workspace / "application_manifest.json"); plan = load_json(workspace / "resume_plan.json")
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            self.respond(404, {"error": str(exc)}); return
        self.respond(200, {"mode": plan.get("application", {}).get("mode", "active_application"), "fit": manifest.get("fit", {})})

    def get_archived_posting(self, lead_id: str) -> None:
        lead_path = self.leads_directory / f"{lead_id}.json"
        if not lead_path.exists():
            self.respond(404, {"error": "Saved job posting was not found."}); return
        try:
            posting = archived_posting(load_json(lead_path))
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self.respond(500, {"error": f"Saved posting is incomplete: {exc}"}); return
        self.respond(200, posting)

    def get_jobs_workspace(self) -> None:
        try:
            data = build_dashboard_data(
                self.leads_directory,
                ROOT / "jobs/analyzed",
                ROOT / "profile/evidence.yaml",
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            self.respond(500, {"error": f"Jobs workspace could not be loaded: {exc}"}); return
        self.respond(200, enrich_jobs_with_workflow(data, self.store))

    def get_profile_status(self) -> None:
        self.respond(200, {"profile_version": profile_version(ROOT / "profile"), "latest_run": self.profile_store.latest()})

    def request_profile_rebuild(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 80 * 1024 * 1024:
                raise ValueError("Upload between 1 byte and 80 MB.")
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                raise ValueError("Use multipart form data for resume uploads.")
            raw = self.rfile.read(length)
            message = BytesParser(policy=policy.default).parsebytes(
                f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + raw
            )
            uploads: list[tuple[str, bytes]] = []; instructions = ""
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                filename = part.get_filename()
                payload = part.get_payload(decode=True) or b""
                if name == "instructions" and not filename:
                    instructions = payload.decode("utf-8", errors="replace")[:5000]
                elif name == "resumes" and filename:
                    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name)[:120]
                    if not safe.casefold().endswith(".pdf") or not payload.startswith(b"%PDF"):
                        raise ValueError(f"{filename} is not a valid PDF.")
                    if len(payload) > 15 * 1024 * 1024:
                        raise ValueError(f"{filename} exceeds the 15 MB per-file limit.")
                    uploads.append((safe, payload))
            if not 1 <= len(uploads) <= 10:
                raise ValueError("Upload between 1 and 10 PDF resumes.")
            names = [f"{index + 1:02d}-{name}" for index, (name, _) in enumerate(uploads)]
            run = self.profile_store.request(names, instructions, profile_version(ROOT / "profile"))
            directory = ROOT / "data/profile-rebuilds" / run["id"] / "uploads"; directory.mkdir(parents=True, exist_ok=True)
            for name, (_, payload) in zip(names, uploads): (directory / name).write_bytes(payload)
            subprocess.Popen([sys.executable, str(ROOT / "scripts/run_profile_rebuild_worker.py"), run["id"]], cwd=ROOT, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (ValueError, OSError) as exc:
            self.respond(400, {"error": str(exc)}); return
        self.respond(202, run)

    def review_profile_rebuild(self, run_id: str, action: str) -> None:
        try:
            run = self.profile_store.get(run_id)
            if run["status"] != "proposal_ready":
                raise ValueError("This profile proposal is not awaiting review.")
            if action == "reject":
                self.respond(200, self.profile_store.update(run_id, "rejected", summary=run["summary"]))
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            items = (run.get("summary") or {}).get("review_items", [])
            selected = payload.get("selected_items", list(range(len(items))))
            if not isinstance(selected, list) or any(not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= len(items) for index in selected):
                raise ValueError("The selected profile changes are invalid.")
            selected = sorted(set(selected))
            selection_path = ROOT / "data/profile-rebuilds" / run_id / "selection.json"
            selection_path.write_text(json.dumps(selected), encoding="utf-8")
            completed = self.profile_store.update(run_id, "approval_running", summary=run["summary"])
            subprocess.Popen([sys.executable, str(ROOT / "scripts/run_profile_approval_worker.py"), run_id], cwd=ROOT, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except KeyError:
            self.respond(404, {"error": "Profile rebuild was not found."}); return
        except (ValueError, OSError) as exc:
            self.respond(409, {"error": str(exc)}); return
        self.respond(202, completed)

    def get_interview_preparation(self, lead_id: str) -> None:
        try:
            path = find_analysis(lead_id).parent / "interview_preparation.json"
        except FileNotFoundError:
            self.respond(404, {"error": "Analyze this job before creating interview preparation."}); return
        if not path.exists(): self.respond(404, {"error": "Interview preparation has not been created yet."}); return
        self.respond(200, load_json(path))

    def prepare_interview(self, lead_id: str) -> None:
        try: package, path = prepare_for_lead(ROOT, lead_id)
        except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError, yaml.YAMLError) as exc:
            self.respond(409, {"error": str(exc)}); return
        self.respond(201, {**package, "saved_path": str(path.relative_to(ROOT))})

    def request_resume_review(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] not in {"resume_draft_completed", "resume_revision_completed", "resume_review_failed"}:
            self.respond(409, {"error": "A validated resume draft is required before review."})
            return
        try:
            run = self.store.transition(run["id"], "resume_review_requested", "user")
        except ValueError as exc:
            self.respond(409, {"error": str(exc)})
            return
        subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/run_resume_review_worker.py"), run["id"]],
            cwd=ROOT, start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.respond(202, run)

    def record_resume_decision(self, lead_id: str) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self.respond(400, {"error": "Invalid resume decision request."})
            return
        action = payload.get("action")
        notes = payload.get("notes", "")
        if action not in {"approve", "request_revision"} or not isinstance(notes, str):
            self.respond(400, {"error": "Choose approve or request_revision and provide text notes."})
            return
        if action == "request_revision" and not notes.strip():
            self.respond(400, {"error": "Tell the agent what you want changed."})
            return
        if action == "approve":
            try:
                review = load_json(find_workspace(lead_id) / "resume_review.json")
            except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
                self.respond(409, {"error": str(exc)})
                return
            summary = review.get("validation_summary", {})
            if review.get("verdict") != "ready" or review.get("review_score", {}).get("total", 0) < 90 or summary.get("critical_count") or summary.get("high_count"):
                self.respond(409, {"error": "Resolve the review findings and reach a Ready verdict before approval."})
                return
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] != "resume_review_completed":
            self.respond(409, {"error": "Complete the resume review before making this decision."})
            return
        status = "resume_approved" if action == "approve" else "resume_revision_requested"
        try:
            run = self.store.transition(
                run["id"], status, "user",
                details={"explicit_user_approval": action == "approve", "notes": notes.strip()},
            )
        except ValueError as exc:
            self.respond(409, {"error": str(exc)})
            return
        self.respond(200, run)

    def request_resume_revision(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] not in {"resume_revision_requested", "resume_revision_failed"}:
            self.respond(409, {"error": "Revision notes and a completed review are required."})
            return
        if run["status"] == "resume_revision_failed":
            try:
                run = self.store.transition(run["id"], "resume_revision_requested", "user", details={"retry": True})
            except ValueError as exc:
                self.respond(409, {"error": str(exc)})
                return
        subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/run_resume_revision_worker.py"), run["id"]],
            cwd=ROOT, start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.respond(202, run)

    def request_resume_finalization(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] not in {"resume_approved", "resume_finalization_failed"}:
            self.respond(409, {"error": "Explicit approval of a Ready resume is required before finalization."})
            return
        try:
            run = self.store.transition(run["id"], "resume_finalization_requested", "user")
        except ValueError as exc:
            self.respond(409, {"error": str(exc)})
            return
        subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/run_resume_finalization_worker.py"), run["id"]], cwd=ROOT,
            start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.respond(202, run)

    def request_resume_pdf(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] not in {"resume_finalization_completed", "resume_pdf_failed"}:
            self.respond(409, {"error": "A finalized resume is required before PDF rendering."})
            return
        try:
            run = self.store.transition(run["id"], "resume_pdf_requested", "user")
        except ValueError as exc:
            self.respond(409, {"error": str(exc)})
            return
        subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/run_resume_pdf_worker.py"), run["id"]], cwd=ROOT,
            start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.respond(202, run)

    def record_resume_pdf_decision(self, lead_id: str) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self.respond(400, {"error": "Invalid PDF decision request."})
            return
        action = payload.get("action")
        notes = payload.get("notes", "")
        if action not in {"approve", "report_issue"} or not isinstance(notes, str):
            self.respond(400, {"error": "Choose approve or report_issue."})
            return
        if action == "report_issue" and not notes.strip():
            self.respond(400, {"error": "Describe the PDF layout issue."})
            return
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] != "resume_pdf_review_required":
            self.respond(409, {"error": "A rendered PDF must be waiting for visual review."})
            return
        if action == "report_issue":
            run = self.store.transition(run["id"], "resume_pdf_failed", "user", details={"visual_issue": notes.strip()}, error=notes.strip())
            self.respond(200, run)
            return
        workspace = find_workspace(lead_id)
        result = subprocess.run(
            [pdf_python(), "scripts/validate_resume_pdf.py", str(workspace), "--schema", str(PDF_SCHEMA),
             "--visual-inspection-passed", "--no-clipping", "--no-overlaps", "--no-broken-glyphs"],
            cwd=ROOT, env=pdf_environment(), capture_output=True, text=True,
        )
        if result.returncode:
            self.respond(409, {"error": (result.stderr or result.stdout or "PDF validation failed.")[-4000:]})
            return
        check_dir = workspace / "pdf_render_check"
        if check_dir.exists():
            shutil.rmtree(check_dir)
        run = self.store.transition(run["id"], "resume_pdf_completed", "user", details={"explicit_visual_approval": True})
        self.respond(200, run)

    def request_cover_letter_plan(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] not in {"resume_pdf_completed", "cover_letter_plan_failed"}:
            self.respond(409, {"error": "A visually approved resume PDF is required before cover letter planning."})
            return
        try:
            run = self.store.transition(run["id"], "cover_letter_plan_requested", "user")
        except ValueError as exc:
            self.respond(409, {"error": str(exc)})
            return
        subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/run_cover_letter_plan_worker.py"), run["id"]], cwd=ROOT,
            start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.respond(202, run)

    def request_cover_letter_draft(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] not in {"cover_letter_plan_completed", "cover_letter_draft_failed"}:
            self.respond(409, {"error": "A validated cover letter plan is required before drafting."})
            return
        workspace = find_workspace(lead_id)
        plan = load_json(workspace / "cover_letter_plan.json")
        if plan.get("recommendation") == "skip":
            if run["status"] != "cover_letter_plan_completed":
                self.respond(409, {"error": "This cover letter plan cannot be skipped from its current state."})
                return
            run = self.store.transition(run["id"], "cover_letter_skipped", "user", details={"plan_recommendation": "skip"})
            manifest_path = workspace / "application_manifest.json"
            manifest = load_json(manifest_path)
            manifest["status"] = "cover_letter_skipped"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            self.respond(200, run)
            return
        try:
            run = self.store.transition(run["id"], "cover_letter_draft_requested", "user")
        except ValueError as exc:
            self.respond(409, {"error": str(exc)})
            return
        subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/run_cover_letter_draft_worker.py"), run["id"]], cwd=ROOT,
            start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.respond(202, run)

    def request_cover_letter_review(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] not in {"cover_letter_draft_completed", "cover_letter_revision_completed", "cover_letter_review_failed"}:
            self.respond(409, {"error": "A validated cover letter draft is required before review."})
            return
        try:
            run = self.store.transition(run["id"], "cover_letter_review_requested", "user")
        except ValueError as exc:
            self.respond(409, {"error": str(exc)})
            return
        subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/run_cover_letter_review_worker.py"), run["id"]], cwd=ROOT,
            start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.respond(202, run)

    def record_cover_letter_decision(self, lead_id: str) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self.respond(400, {"error": "Invalid cover letter decision request."})
            return
        action = payload.get("action")
        notes = payload.get("notes", "")
        if action not in {"approve", "request_revision"} or not isinstance(notes, str):
            self.respond(400, {"error": "Choose approve or request_revision."})
            return
        if action == "request_revision" and not notes.strip():
            self.respond(400, {"error": "Tell the agent what you want changed."})
            return
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] != "cover_letter_review_completed":
            self.respond(409, {"error": "Complete the cover letter review before making this decision."})
            return
        review = load_json(find_workspace(lead_id) / "cover_letter_review.json")
        blocking = any(item.get("severity") in {"critical", "high"} for item in review.get("findings", []))
        if action == "request_revision" and review.get("verdict") == "ready":
            self.respond(409, {"error": "This review is Ready and does not authorize a revision. Approve the letter instead."})
            return
        if action == "approve" and (review.get("verdict") != "ready" or review.get("score", 0) < 90 or blocking):
            self.respond(409, {"error": "Resolve the review findings and reach a Ready verdict before approval."})
            return
        status = "cover_letter_approved" if action == "approve" else "cover_letter_revision_requested"
        run = self.store.transition(
            run["id"], status, "user",
            details={"explicit_user_approval": action == "approve", "notes": notes.strip()},
        )
        self.respond(200, run)

    def request_cover_letter_revision(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] not in {"cover_letter_revision_requested", "cover_letter_revision_failed"}:
            self.respond(409, {"error": "A non-ready review with revision notes is required."})
            return
        if run["status"] == "cover_letter_revision_failed":
            try:
                run = self.store.transition(run["id"], "cover_letter_revision_requested", "user", details={"retry": True})
            except ValueError as exc:
                self.respond(409, {"error": str(exc)})
                return
        subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/run_cover_letter_revision_worker.py"), run["id"]], cwd=ROOT,
            start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.respond(202, run)

    def request_cover_letter_finalization(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] not in {"cover_letter_approved", "cover_letter_finalization_failed"}:
            self.respond(409, {"error": "Explicit approval of a Ready cover letter is required."})
            return
        try:
            run = self.store.transition(run["id"], "cover_letter_finalization_requested", "user")
        except ValueError as exc:
            self.respond(409, {"error": str(exc)})
            return
        subprocess.Popen([sys.executable, str(ROOT / "scripts/run_cover_letter_finalization_worker.py"), run["id"]], cwd=ROOT, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.respond(202, run)

    def request_cover_letter_pdf(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] not in {"cover_letter_finalization_completed", "cover_letter_pdf_failed"}:
            self.respond(409, {"error": "A finalized cover letter is required before PDF rendering."})
            return
        try:
            run = self.store.transition(run["id"], "cover_letter_pdf_requested", "user")
        except ValueError as exc:
            self.respond(409, {"error": str(exc)})
            return
        subprocess.Popen([sys.executable, str(ROOT / "scripts/run_cover_letter_pdf_worker.py"), run["id"]], cwd=ROOT, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.respond(202, run)

    def record_cover_letter_pdf_decision(self, lead_id: str) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self.respond(400, {"error": "Invalid PDF decision request."}); return
        action, notes = payload.get("action"), payload.get("notes", "")
        if action not in {"approve", "report_issue"} or not isinstance(notes, str):
            self.respond(400, {"error": "Choose approve or report_issue."}); return
        if action == "report_issue" and not notes.strip():
            self.respond(400, {"error": "Describe the PDF layout issue."}); return
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] != "cover_letter_pdf_review_required":
            self.respond(409, {"error": "A rendered cover letter PDF must be waiting for review."}); return
        if action == "report_issue":
            run = self.store.transition(run["id"], "cover_letter_pdf_failed", "user", details={"visual_issue": notes.strip()}, error=notes.strip())
            self.respond(200, run); return
        result = subprocess.run([pdf_python(), "scripts/release_cover_letter_pdf.py", lead_id], cwd=ROOT, env=pdf_environment(), capture_output=True, text=True)
        if result.returncode:
            self.respond(409, {"error": (result.stderr or result.stdout or "Cover letter PDF release failed.")[-4000:]}); return
        run = self.store.transition(run["id"], "cover_letter_pdf_completed", "user", details={"explicit_visual_approval": True})
        self.respond(200, run)

    def request_application_package(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] not in {"cover_letter_pdf_completed", "cover_letter_skipped", "application_package_failed"}:
            self.respond(409, {"error": "Approved application documents are required before packaging."}); return
        try:
            run = self.store.transition(run["id"], "application_package_requested", "user")
        except ValueError as exc:
            self.respond(409, {"error": str(exc)}); return
        subprocess.Popen([sys.executable, str(ROOT / "scripts/run_application_package_worker.py"), run["id"]], cwd=ROOT, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.respond(202, run)

    def request_resume_plan(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] not in {"strategy_completed", "resume_plan_failed"}:
            self.respond(409, {"error": "A validated candidate strategy is required before resume planning."})
            return
        try:
            run = self.store.transition(run["id"], "resume_plan_requested", "user")
        except ValueError as exc:
            self.respond(409, {"error": str(exc)})
            return
        subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/run_resume_plan_worker.py"), run["id"]],
            cwd=ROOT, start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.respond(202, run)

    def record_decision(self, lead_id: str) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self.respond(400, {"error": "Invalid decision request."})
            return
        decision = payload.get("decision")
        if decision not in {"pursue", "pass", "decide_later"}:
            self.respond(400, {"error": "Decision must be pursue, pass, or decide_later."})
            return

        lead_path = self.leads_directory / f"{lead_id}.json"
        if not lead_path.exists():
            self.respond(404, {"error": "Job lead not found."})
            return
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] == "analysis_failed":
            leads = load_leads(self.leads_directory)
            analyses = load_valid_analyses(ROOT / "jobs/analyzed", ROOT / "profile/evidence.yaml")
            results, _ = join_results(leads, analyses)
            match = next((result for result in results if result.lead["lead_id"] == lead_id), None)
            if match is None:
                self.respond(409, {"error": "A validated fit analysis is required before deciding."})
                return
            run = self.store.record_completed_analysis(
                lead_id, str(match.analysis_path), actor="workflow_api"
            )
        if run["status"] == decision:
            self.respond(200, run)
            return
        try:
            run = self.store.transition(
                run["id"], decision, "user", details={"explicit_user_decision": True}
            )
        except ValueError as exc:
            self.respond(409, {"error": str(exc)})
            return

        lead = load_json(lead_path)
        lead["status"]["reviewed"] = True
        note = f"User decision: {decision.replace('_', ' ')}."
        notes = lead["status"].setdefault("notes", [])
        notes[:] = [item for item in notes if not item.startswith("User decision:")]
        notes.append(note)
        lead_path.write_text(json.dumps(lead, indent=2) + "\n", encoding="utf-8")
        self.respond(200, run)

    def request_strategy(self, lead_id: str) -> None:
        run = self.store.latest_for_lead(lead_id)
        if run is None or run["status"] not in {"pursue", "strategy_failed"}:
            self.respond(409, {"error": "An explicit Pursue decision is required before strategy."})
            return
        try:
            run = self.store.transition(run["id"], "strategy_requested", "user")
        except ValueError as exc:
            self.respond(409, {"error": str(exc)})
            return
        subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/run_strategy_worker.py"), run["id"]],
            cwd=ROOT, start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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
    WorkflowHandler.discovery_store = DiscoveryStore(args.database)
    WorkflowHandler.alert_store = AlertInboxStore(args.database)
    WorkflowHandler.profile_store = ProfileRebuildStore(args.database)
    WorkflowHandler.leads_directory = args.leads
    threading.Thread(target=scheduled_discovery_loop, args=(args.database,), daemon=True).start()
    threading.Thread(target=gmail_alert_loop, args=(args.database,), daemon=True).start()
    server = HTTPServer((args.host, args.port), WorkflowHandler)
    print(f"Workflow API: http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

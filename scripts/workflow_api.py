#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from write_resume_with_codex import find_workspace
from prepare_application_answers import apply_answer_review, validate_form_fill_confirmation
from run_resume_pdf_worker import PDF_SCHEMA, pdf_environment, pdf_python
from surface_fit_queue import join_results, load_leads, load_valid_analyses
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
        self.respond(404, {"error": "Not found."})

    def do_POST(self) -> None:
        parts = urlparse(self.path).path.strip("/").split("/")
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
        source_url = payload.get("source_url", "")
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
            session = {"schema_version": "1.0", "lead_id": lead_id, "source_url": source_url.strip(), "status": "form_filling_started", "completed_question_ids": [], "documents_checked": False, "submit_clicked": False}
            (workspace / "form_fill_session.json").write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
            run = self.store.transition(run["id"], "form_filling_started", "user", details={"assisted_mode": True, "submit_clicked": False})
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
            self.respond(409, {"error": str(exc)}); return
        self.respond(200, run)

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
            run = self.store.transition(run["id"], "resume_draft_requested", "user")
        except ValueError as exc:
            self.respond(409, {"error": str(exc)})
            return
        subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/run_resume_draft_worker.py"), run["id"]],
            cwd=ROOT, start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.respond(202, run)

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
    WorkflowHandler.leads_directory = args.leads
    server = HTTPServer((args.host, args.port), WorkflowHandler)
    print(f"Workflow API: http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

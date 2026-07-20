#!/usr/bin/env python3

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


STATUSES = {"submitted", "follow_up_due", "interview", "rejected", "withdrawn", "offer", "closed"}


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def initial_tracker(lead_id: str, company: str, role: str, confirmation: str) -> dict:
    submitted = timestamp()
    follow_up = (date.today() + timedelta(days=7)).isoformat()
    return {"schema_version": "1.0", "lead_id": lead_id, "company": company, "role": role, "submitted_at_utc": submitted, "confirmation_evidence": confirmation, "confirmation_reference": "", "application_status": "submitted", "follow_up_date": follow_up, "expected_response_date": None, "interview_stage": None, "next_action": f"Follow up if there is no response by {follow_up}.", "notes": "", "history": [{"at_utc": submitted, "status": "submitted", "note": "Employer submission confirmation recorded."}]}


def optional_date(value: object, field: str) -> str | None:
    if value in (None, ""): return None
    if not isinstance(value, str): raise ValueError(f"{field} must be a date.")
    try: date.fromisoformat(value)
    except ValueError as exc: raise ValueError(f"{field} must use YYYY-MM-DD.") from exc
    return value


def update_tracker(tracker: dict, payload: dict) -> dict:
    status = payload.get("application_status")
    if status not in STATUSES: raise ValueError("Choose a valid application status.")
    for field in ("confirmation_reference", "interview_stage", "next_action", "notes"):
        value = payload.get(field, "")
        if value is not None and not isinstance(value, str): raise ValueError(f"{field} must be text.")
        tracker[field] = value.strip() if isinstance(value, str) else None
    tracker["follow_up_date"] = optional_date(payload.get("follow_up_date"), "follow_up_date")
    tracker["expected_response_date"] = optional_date(payload.get("expected_response_date"), "expected_response_date")
    previous = tracker.get("application_status")
    tracker["application_status"] = status
    if status != previous:
        tracker.setdefault("history", []).append({"at_utc": timestamp(), "status": status, "note": tracker.get("notes") or f"Status changed from {previous} to {status}."})
    return tracker

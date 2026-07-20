#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from validate_job_lead import load_json
from write_resume_with_codex import find_workspace


PROTECTED = {
    "salary": ("salary", "compensation", "pay expectation", "desired pay"),
    "relocation": ("relocat",),
    "travel": ("travel", "driver", "vehicle", "licence", "license"),
    "work_authorization": ("authorized to work", "work authorization", "sponsor", "visa", "citizen"),
    "legal_declaration": ("criminal", "convict", "security clearance", "background check", "legal declaration"),
    "sensitive_personal": ("disability", "medical", "gender", "race", "ethnic", "veteran", "indigenous", "sexual orientation", "pronoun"),
    "references": ("reference",),
    "start_date": ("start date", "available to start", "notice period"),
}


def classify(question: str) -> str:
    lowered = question.lower()
    for category, phrases in PROTECTED.items():
        if any(phrase in lowered for phrase in phrases):
            return category
    if any(term in lowered for term in ("resume", "cv", "cover letter", "upload")):
        return "attachment"
    return "narrative"


def strategy_for(question: str, strategies: list[dict]) -> dict | None:
    words = set(re.findall(r"[a-z]{4,}", question.lower()))
    best: tuple[int, dict] | None = None
    for item in strategies:
        haystack = f"{item.get('category', '')} {item.get('central_message', '')}".lower()
        score = sum(word in haystack for word in words)
        if best is None or score > best[0]:
            best = (score, item)
    return best[1] if best and best[0] else (strategies[0] if strategies else None)


def prepare(lead_id: str) -> Path:
    workspace = find_workspace(lead_id)
    form = load_json(workspace / "application_form.json")
    strategy = load_json(workspace / "candidate_strategy.json")
    answer_strategies = strategy.get("application_answer_strategy", [])
    answers = []
    for item in form["questions"]:
        category = classify(item["question"])
        matched = strategy_for(item["question"], answer_strategies) if category == "narrative" else None
        if category == "attachment":
            status, answer, evidence, reason = "attachment_ready", None, [], "Use only the approved files in the application package."
        elif category != "narrative":
            status, answer, evidence, reason = "requires_user_input", None, [], "This answer is sensitive, legal, logistical, or creates a commitment and must not be inferred."
        elif matched:
            status = "drafted"
            answer = matched.get("central_message")
            evidence = matched.get("recommended_ids", [])
            reason = f"Drafted from the verified candidate-strategy category: {matched.get('category', 'application answer')}."
        else:
            status, answer, evidence, reason = "requires_user_input", None, [], "No verified answer strategy supports a draft."
        answers.append({"question_id": item["question_id"], "question": item["question"], "category": category, "status": status, "proposed_answer": answer, "evidence_ids": evidence, "reason": reason, "reviewed": False})
    payload = {"schema_version": "1.0", "lead_id": lead_id, "source_url": form.get("source_url"), "answers": answers, "submission_authorized": False}
    path = workspace / "application_answers.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("lead_id"); args = parser.parse_args()
    print(prepare(args.lead_id)); return 0


if __name__ == "__main__":
    raise SystemExit(main())

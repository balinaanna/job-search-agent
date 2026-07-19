#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from collections import Counter
from pathlib import Path
from jsonschema import Draft202012Validator

def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return value

def expected_verdict(score: int) -> str:
    if score >= 90: return "ready"
    if score >= 80: return "minor_revision"
    if score >= 65: return "major_revision"
    return "rewrite_required"

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "--schema", type=Path,
        default=Path.home() / ".hermes/skills/cover-letter-reviewer/references/cover-letter-review-schema.json"
    )
    args = parser.parse_args()
    w = args.workspace

    try:
        manifest = load_json(w / "application_manifest.json")
        plan = load_json(w / "cover_letter_plan.json")
        trace = load_json(w / "cover_letter_trace.json")
        review = load_json(w / "cover_letter_review.json")
        schema = load_json(args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors = []
    for error in Draft202012Validator(schema).iter_errors(review):
        loc = ".".join(str(p) for p in error.path) or "<root>"
        errors.append(f"schema {loc}: {error.message}")

    app_id = manifest.get("application_id")
    for name, value in [
        ("plan", plan.get("application_id")),
        ("trace", trace.get("application_id")),
        ("review", review.get("application_id")),
    ]:
        if value != app_id:
            errors.append(f"{name} application ID does not match manifest.")

    if manifest.get("status") != "cover_letter_review":
        errors.append("Manifest status must be cover_letter_review.")
    if trace.get("manifest_status") != "cover_letter_drafting":
        errors.append("Cover letter trace must be cover_letter_drafting.")

    breakdown = review.get("score_breakdown", {})
    total = sum(breakdown.values())
    if total != review.get("score"):
        errors.append(f"Score breakdown totals {total}, but score is {review.get('score')}.")

    score = review.get("score", 0)
    verdict = review.get("verdict")
    if verdict != expected_verdict(score):
        errors.append(f"Verdict {verdict} does not match score {score}; expected {expected_verdict(score)}.")

    paragraph_ids = {p.get("paragraph_id") for p in plan.get("paragraphs", [])}
    finding_ids = set()
    for f in review.get("findings", []):
        fid = f.get("finding_id")
        if fid in finding_ids:
            errors.append(f"Duplicate finding ID: {fid}")
        finding_ids.add(fid)
        if f.get("paragraph_id") not in paragraph_ids:
            errors.append(f"{fid} references unknown paragraph {f.get('paragraph_id')}.")

    for s in review.get("strengths", []):
        for pid in s.get("paragraph_ids", []):
            if pid not in paragraph_ids:
                errors.append(f"{s.get('strength_id')} references unknown paragraph {pid}.")

    brief = review.get("revision_brief", {})
    for pid in brief.get("authorized_paragraph_ids", []):
        if pid not in paragraph_ids:
            errors.append(f"Revision brief references unknown paragraph {pid}.")
    for fid in brief.get("priority_order", []):
        if fid not in finding_ids:
            errors.append(f"Revision priority references unknown finding {fid}.")

    counts = Counter(f.get("severity") for f in review.get("findings", []))
    if verdict == "ready":
        if counts["critical"] or counts["high"]:
            errors.append("Ready verdict cannot contain critical or high findings.")
        if brief.get("authorized_paragraph_ids"):
            errors.append("Ready verdict should not authorize revisions.")
    if verdict == "minor_revision" and counts["critical"]:
        errors.append("Minor revision verdict cannot contain critical findings.")

    if not (w / "cover_letter_review.md").exists():
        errors.append("Missing cover_letter_review.md.")

    if errors:
        print("Validation failed:")
        for e in errors:
            print(f"- {e}")
        return 1

    print("Cover letter review validation passed.")
    print(f"Application: {manifest['company']} — {manifest['role']}")
    print(f"Score: {score}/100")
    print(f"Verdict: {verdict}")
    print(
        f"Findings: {counts['critical']} critical, {counts['high']} high, "
        f"{counts['medium']} medium, {counts['low']} low"
    )
    print(f"Manifest status: {manifest['status']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

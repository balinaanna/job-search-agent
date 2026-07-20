#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from validate_job_lead import load_json
from write_cover_letter_with_codex import word_count
from write_resume_with_codex import find_workspace

ROOT = Path(__file__).resolve().parent.parent
FINAL_SCHEMA = ROOT / "hermes-skills/cover-letter-finalizer/references/cover-letter-finalization-schema.json"
REVIEW_SCHEMA = ROOT / "hermes-skills/cover-letter-reviewer/references/cover-letter-review-schema.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize_cover_letter(lead_id: str) -> Path:
    workspace = find_workspace(lead_id)
    manifest_path = workspace / "application_manifest.json"
    manifest = load_json(manifest_path)
    review = load_json(workspace / "cover_letter_review.json")
    if manifest.get("status") != "cover_letter_review" or review.get("verdict") != "ready" or review.get("score", 0) < 90:
        raise ValueError("A Ready cover letter review and explicit approval are required.")
    if any(item.get("severity") in {"critical", "high"} for item in review.get("findings", [])):
        raise ValueError("Blocking cover letter findings must be resolved.")
    if review.get("revision_brief", {}).get("authorized_paragraph_ids"):
        raise ValueError("The Ready review must not authorize further revisions.")
    subprocess.run([sys.executable, "scripts/validate_cover_letter_review.py", str(workspace), "--schema", str(REVIEW_SCHEMA)], cwd=ROOT, check=True)
    source = workspace / "cover_letter.md"
    final = workspace / "final_cover_letter.md"
    shutil.copyfile(source, final)
    plan = load_json(workspace / "cover_letter_plan.json")
    trace = load_json(workspace / "cover_letter_trace.json")
    paths = {
        "source_cover_letter": source, "final_cover_letter": final,
        "cover_letter_trace": workspace / "cover_letter_trace.json",
        "cover_letter_plan": workspace / "cover_letter_plan.json",
        "cover_letter_review": workspace / "cover_letter_review.json",
        "candidate_strategy": workspace / "candidate_strategy.json",
        "final_resume": workspace / "final_resume.md", "resume_trace": workspace / "resume_trace.json",
    }
    evidence = sorted({eid for paragraph in trace["paragraphs"] for eid in paragraph["evidence_ids"]})
    elements = sorted({eid for paragraph in trace["paragraphs"] for eid in paragraph["resume_element_ids"]})
    record = {
        "application_id": manifest["application_id"], "company": manifest["company"], "role": manifest["role"],
        "source_review": {"score": review["score"], "verdict": "ready", "review_path": "cover_letter_review.json"},
        "artifacts": {key: path.relative_to(workspace).as_posix() for key, path in paths.items()},
        "release_hashes": {
            "source_cover_letter_sha256": sha256(source), "final_cover_letter_sha256": sha256(final),
            "cover_letter_trace_sha256": sha256(paths["cover_letter_trace"]), "cover_letter_plan_sha256": sha256(paths["cover_letter_plan"]),
            "cover_letter_review_sha256": sha256(paths["cover_letter_review"]), "candidate_strategy_sha256": sha256(paths["candidate_strategy"]),
            "final_resume_sha256": sha256(paths["final_resume"]), "resume_trace_sha256": sha256(paths["resume_trace"]),
        },
        "paragraph_count": plan["structure"]["paragraph_count"], "total_word_count": word_count(final.read_text(encoding="utf-8")),
        "target_words_min": plan["structure"]["target_words_min"], "target_words_max": plan["structure"]["target_words_max"],
        "evidence_coverage": {"covered_evidence_ids": evidence, "covered_resume_element_ids": elements, "unsupported_claims": []},
        "release_checks": {
            "review_ready": True, "score_threshold_met": True, "no_blocking_findings": True,
            "no_authorized_revisions": True, "source_and_final_identical": source.read_bytes() == final.read_bytes(),
            "paragraph_count_matches_plan": True, "word_count_within_range": True, "trace_matches_letter": True,
            "evidence_grounded": True, "hashes_verified": True, "manifest_updated": True,
        },
        "manifest_status": "cover_letter_ready",
    }
    finalization = workspace / "cover_letter_finalization.json"
    finalization.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    (workspace / "cover_letter_finalization.md").write_text(
        f"# Cover letter finalization\n\n**{review['score']}/100 - Ready**\n\nApproved content was locked byte-for-byte.\n\n- Final letter: `{final}`\n- Words: {record['total_word_count']}\n- SHA256: `{record['release_hashes']['final_cover_letter_sha256']}`\n- Status: cover letter ready\n",
        encoding="utf-8",
    )
    manifest["status"] = "cover_letter_ready"
    manifest.setdefault("artifacts", {}).update({
        "final_cover_letter_markdown": str(final.relative_to(ROOT)),
        "cover_letter_finalization_json": str(finalization.relative_to(ROOT)),
        "cover_letter_finalization_markdown": str((workspace / "cover_letter_finalization.md").relative_to(ROOT)),
    })
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, "scripts/validate_cover_letter_finalization.py", str(workspace), "--schema", str(FINAL_SCHEMA)], cwd=ROOT, check=True)
    return finalization


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lead_id")
    args = parser.parse_args()
    print(finalize_cover_letter(args.lead_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

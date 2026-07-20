#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from validate_job_lead import load_json
from write_resume_with_codex import find_workspace

ROOT = Path(__file__).resolve().parent.parent
FINAL_SCHEMA = ROOT / "hermes-skills/resume-finalizer/references/resume-finalization-schema.json"
REVIEW_SCHEMA = ROOT / "hermes-skills/resume-reviewer/references/resume-review-schema.json"
TRACE_SCHEMA = ROOT / "hermes-skills/resume-writer/references/resume-trace-schema.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def next_version(workspace: Path) -> int:
    versions = workspace / "versions"
    number = 1
    while any((versions / name.format(number)).exists() for name in (
        "final_resume_v{}.md", "final_resume_trace_v{}.json", "final_resume_review_v{}.json",
    )):
        number += 1
    return number


def render_summary(record: dict, manifest: dict) -> str:
    return f"""# Resume finalization

## Result

Approved resume content locked without modification.

## Application

- {manifest['company']} - {manifest['role']}
- Review score: {record['review']['score']}/100
- Final version: {record['final_version']}

## Locked artifacts

- Final resume: `{record['output_paths']['final_resume']}`
- Snapshot: `{record['output_paths']['snapshot_resume']}`

## Verification

- Content hashes match: yes
- Manifest status: ready

## Next step

Render and inspect the PDF.
"""


def finalize_resume(lead_id: str) -> Path:
    workspace = find_workspace(lead_id)
    manifest_path = workspace / "application_manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("status") != "review":
        raise ValueError("The approved resume must still be in review state before finalization.")
    review = load_json(workspace / "resume_review.json")
    summary = review.get("validation_summary", {})
    if review.get("verdict") != "ready" or review.get("review_score", {}).get("total", 0) < 90:
        raise ValueError("The recruiter review must be ready with a score of at least 90.")
    if summary.get("critical_count") or summary.get("high_count"):
        raise ValueError("Critical and high review findings must be resolved before finalization.")
    revision_path = workspace / "resume_revision.json"
    if revision_path.exists() and load_json(revision_path).get("unresolved_conflicts"):
        raise ValueError("Unresolved revision conflicts must be cleared before finalization.")
    subprocess.run(
        [sys.executable, "scripts/validate_resume_draft.py", str(workspace), "--schema", str(TRACE_SCHEMA), "--expected-status", "review"],
        cwd=ROOT, check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/validate_resume_review.py", str(workspace), "--schema", str(REVIEW_SCHEMA)],
        cwd=ROOT, check=True,
    )
    version = next_version(workspace)
    versions = workspace / "versions"
    versions.mkdir(exist_ok=True)
    resume = workspace / "resume.md"
    trace = workspace / "resume_trace.json"
    review_path = workspace / "resume_review.json"
    plan = workspace / "resume_plan.json"
    final_resume = workspace / "final_resume.md"
    snapshot_resume = versions / f"final_resume_v{version}.md"
    snapshot_trace = versions / f"final_resume_trace_v{version}.json"
    snapshot_review = versions / f"final_resume_review_v{version}.json"
    for target in (snapshot_resume, snapshot_trace, snapshot_review):
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite release snapshot: {target}")
    shutil.copyfile(resume, final_resume)
    shutil.copyfile(resume, snapshot_resume)
    shutil.copyfile(trace, snapshot_trace)
    shutil.copyfile(review_path, snapshot_review)
    finalization_md = workspace / "resume_finalization.md"
    record = {
        "application_id": manifest["application_id"],
        "final_version": version,
        "review": {"score": review["review_score"]["total"], "verdict": "ready", "critical_count": 0, "high_count": 0},
        "source_paths": {"resume": str(resume), "trace": str(trace), "review": str(review_path), "plan": str(plan)},
        "output_paths": {
            "final_resume": str(final_resume), "snapshot_resume": str(snapshot_resume),
            "snapshot_trace": str(snapshot_trace), "snapshot_review": str(snapshot_review),
            "finalization_markdown": str(finalization_md),
        },
        "hashes": {
            "source_resume_sha256": sha256(resume), "final_resume_sha256": sha256(final_resume),
            "snapshot_resume_sha256": sha256(snapshot_resume), "source_trace_sha256": sha256(trace),
            "snapshot_trace_sha256": sha256(snapshot_trace), "source_review_sha256": sha256(review_path),
            "snapshot_review_sha256": sha256(snapshot_review), "plan_sha256": sha256(plan),
        },
        "release_gates": {
            "manifest_was_review": True, "review_ready": True, "score_at_least_90": True,
            "no_critical_findings": True, "no_high_findings": True, "draft_validation_passed": True,
            "review_validation_passed": True, "no_unresolved_revision_conflicts": True,
            "content_hashes_match": sha256(resume) == sha256(final_resume) == sha256(snapshot_resume),
        },
        "finalized_at": datetime.now(timezone.utc).isoformat(), "manifest_status": "ready",
        "next_permitted_workflows": ["resume-pdf-renderer", "cover-letter-planner"],
    }
    finalization = workspace / "resume_finalization.json"
    finalization.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    finalization_md.write_text(render_summary(record, manifest), encoding="utf-8")
    manifest["status"] = "ready"
    artifacts = manifest.setdefault("artifacts", {})
    artifacts.update({
        "final_resume_markdown": str(final_resume.relative_to(ROOT)),
        "resume_finalization_json": str(finalization.relative_to(ROOT)),
        "resume_finalization_markdown": str(finalization_md.relative_to(ROOT)),
    })
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    subprocess.run(
        [sys.executable, "scripts/validate_resume_finalization.py", str(workspace), "--schema", str(FINAL_SCHEMA)],
        cwd=ROOT, check=True,
    )
    return finalization


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lead_id")
    args = parser.parse_args()
    print(finalize_resume(args.lead_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

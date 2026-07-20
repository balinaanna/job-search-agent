#!/usr/bin/env python3

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from workflow_store import WorkflowStore
from write_resume_with_codex import find_workspace

ROOT = Path(__file__).resolve().parent.parent
BUNDLED_PYTHON = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
PDF_SCHEMA = ROOT / "hermes-skills/resume-pdf-renderer/references/resume-pdf-release-schema.json"


def pdf_python() -> str:
    configured = os.environ.get("PDF_PYTHON")
    if configured:
        return configured
    return str(BUNDLED_PYTHON) if BUNDLED_PYTHON.exists() else sys.executable


def main() -> int:
    run_id = sys.argv[1]
    store = WorkflowStore(ROOT / "data/jobs.db")
    run = store.transition(run_id, "resume_pdf_running", "resume_pdf_worker")
    workspace = find_workspace(run["lead_id"])
    check_dir = workspace / "pdf_render_check"
    try:
        python = pdf_python()
        subprocess.run([python, "scripts/render_resume_pdf.py", str(workspace)], cwd=ROOT, check=True, capture_output=True, text=True)
        check_dir.mkdir(exist_ok=True)
        subprocess.run(["pdftoppm", "-png", "-r", "180", str(workspace / "final_resume.pdf"), str(check_dir / "page")], cwd=ROOT, check=True, capture_output=True, text=True)
        validation = subprocess.run(
            [python, "scripts/validate_resume_pdf.py", str(workspace), "--schema", str(PDF_SCHEMA)],
            cwd=ROOT, capture_output=True, text=True,
        )
        if validation.returncode not in {0, 2}:
            raise subprocess.CalledProcessError(validation.returncode, validation.args, validation.stdout, validation.stderr)
        store.transition(
            run_id, "resume_pdf_review_required", "resume_pdf_worker",
            details={"text_fidelity_validated": True, "rendered_pages": len(list(check_dir.glob("page-*.png")))},
            result_path=str(workspace / "final_resume.pdf"),
        )
        return 0
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or str(exc)).strip()
        store.transition(run_id, "resume_pdf_failed", "resume_pdf_worker", error=stderr[-4000:])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

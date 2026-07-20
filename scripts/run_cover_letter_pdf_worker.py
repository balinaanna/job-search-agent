#!/usr/bin/env python3

from __future__ import annotations
import re, shutil, subprocess, sys
from pathlib import Path
from run_resume_pdf_worker import pdf_python
from workflow_store import WorkflowStore
from write_resume_with_codex import find_workspace

ROOT = Path(__file__).resolve().parent.parent

def normalize(text: str) -> str:
    text = re.sub(r"[*_#>`]", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", " ", text).strip()

def main() -> int:
    run_id = sys.argv[1]
    store = WorkflowStore(ROOT / "data/jobs.db")
    run = store.transition(run_id, "cover_letter_pdf_running", "cover_letter_pdf_worker")
    workspace = find_workspace(run["lead_id"])
    render_dir = workspace / ".cover_letter_pdf_render"
    try:
        python = pdf_python()
        if render_dir.exists(): shutil.rmtree(render_dir)
        subprocess.run([python, "scripts/render_cover_letter_pdf.py", str(workspace)], cwd=ROOT, check=True, capture_output=True, text=True)
        check = subprocess.run([python, "-c", "from pypdf import PdfReader; import sys; print('\\n'.join((p.extract_text() or '') for p in PdfReader(sys.argv[1]).pages))", str(workspace / "final_cover_letter.pdf")], cwd=ROOT, check=True, capture_output=True, text=True)
        source = (workspace / "final_cover_letter.md").read_text(encoding="utf-8")
        if normalize(source) != normalize(check.stdout):
            raise ValueError("Rendered PDF text does not match the finalized cover letter.")
        render_dir.mkdir(exist_ok=True)
        subprocess.run(["pdftoppm", "-png", "-r", "200", str(workspace / "final_cover_letter.pdf"), str(render_dir / "page")], cwd=ROOT, check=True, capture_output=True, text=True)
        pages = len(list(render_dir.glob("page-*.png")))
        if not pages:
            raise ValueError("PDF page rendering produced no inspection images.")
        store.transition(run_id, "cover_letter_pdf_review_required", "cover_letter_pdf_worker", details={"text_fidelity_validated": True, "rendered_pages": pages}, result_path=str(workspace / "final_cover_letter.pdf"))
        return 0
    except (subprocess.CalledProcessError, ValueError) as exc:
        stderr = (exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)) or str(exc)
        store.transition(run_id, "cover_letter_pdf_failed", "cover_letter_pdf_worker", error=stderr.strip()[-4000:])
        return 1

if __name__ == "__main__": raise SystemExit(main())

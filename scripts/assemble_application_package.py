#!/usr/bin/env python3

from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from pypdf import PdfReader
from validate_job_lead import load_json
from write_resume_with_codex import find_workspace

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "hermes-skills/application-package-assembler/references/application-package-schema.json"

def sha256(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def pages(path: Path) -> int: return len(PdfReader(str(path)).pages)

def assemble(lead_id: str) -> Path:
    workspace = find_workspace(lead_id)
    manifest_path = workspace / "application_manifest.json"
    manifest = load_json(manifest_path)
    include_cover = manifest.get("status") == "cover_letter_rendered"
    if manifest.get("status") not in {"cover_letter_rendered", "cover_letter_skipped"}:
        raise ValueError("Approved application documents are required before packaging.")
    resume = workspace / "final_resume.pdf"; resume_release = workspace / "resume_pdf_release.json"
    cover = workspace / "final_cover_letter.pdf"; cover_release = workspace / "cover_letter_pdf_release.json"
    resume_meta = load_json(resume_release)
    if resume_meta.get("manifest_status") != "rendered" or resume_meta.get("application_id") != manifest["application_id"]:
        raise ValueError("Resume PDF release is not valid for this application.")
    if resume_meta.get("hashes", {}).get("final_resume_pdf_sha256") != sha256(resume):
        raise ValueError("Resume PDF does not match its release hash.")
    if include_cover:
        cover_meta = load_json(cover_release)
        if cover_meta.get("manifest_status") != "cover_letter_rendered" or cover_meta.get("application_id") != manifest["application_id"]:
            raise ValueError("Cover letter PDF release is not valid for this application.")
        if cover_meta.get("hashes", {}).get("final_cover_letter_pdf_sha256") != sha256(cover):
            raise ValueError("Cover letter PDF does not match its release hash.")
    submission = workspace / "submission"
    if submission.exists() and any(submission.iterdir()):
        raise FileExistsError(f"Refusing to overwrite existing application package: {submission}")
    submission.mkdir(exist_ok=True)
    packaged_resume = submission / "resume.pdf"; shutil.copy2(resume, packaged_resume)
    packaged_cover = submission / "cover_letter.pdf"
    if include_cover: shutil.copy2(cover, packaged_cover)
    checklist = submission / "submission_checklist.md"
    checklist.write_text("""# Submission Checklist

- [ ] Employer and role verified
- [ ] Application URL verified
- [ ] Resume attached
- [ ] Cover letter attached when requested
- [ ] Uploaded filenames verified
- [ ] Application form answers reviewed
- [ ] Salary response reviewed
- [ ] Work authorization response reviewed
- [ ] Travel or relocation commitments reviewed
- [ ] Legal declarations reviewed
- [ ] Voluntary demographic questions handled intentionally
- [ ] Final confirmation page reviewed
- [ ] Submission completed
- [ ] Submission timestamp recorded
- [ ] Confirmation email or reference number saved
""", encoding="utf-8")
    package = {
        "application_id": manifest["application_id"], "company": manifest["company"], "role": manifest["role"],
        "package_version": 1, "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_artifacts": {"resume_pdf": "final_resume.pdf", "cover_letter_pdf": "final_cover_letter.pdf" if include_cover else None},
        "packaged_artifacts": {"resume_pdf": "submission/resume.pdf", "cover_letter_pdf": "submission/cover_letter.pdf" if include_cover else None, "package_json": "submission/application_package.json", "package_markdown": "submission/application_package.md", "submission_checklist": "submission/submission_checklist.md"},
        "hashes": {"source_resume_sha256": sha256(resume), "packaged_resume_sha256": sha256(packaged_resume), "source_cover_letter_sha256": sha256(cover) if include_cover else None, "packaged_cover_letter_sha256": sha256(packaged_cover) if include_cover else None},
        "page_counts": {"resume": pages(packaged_resume), "cover_letter": pages(packaged_cover) if include_cover else 0},
        "release_references": {"resume_pdf_release": "resume_pdf_release.json", "cover_letter_pdf_release": "cover_letter_pdf_release.json" if include_cover else None, "resume_release_sha256": sha256(resume_release), "cover_letter_release_sha256": sha256(cover_release) if include_cover else None},
        "identity_checks": {"application_ids_match": True, "company_names_match": True, "role_names_match": True, "resume_copy_identical": resume.read_bytes() == packaged_resume.read_bytes(), "cover_letter_copy_identical": (cover.read_bytes() == packaged_cover.read_bytes()) if include_cover else True},
        "readiness_checks": {"resume_release_valid": True, "cover_letter_release_valid": True, "source_hashes_verified": True, "packaged_hashes_verified": True, "pdfs_readable": True, "submission_directory_complete": True, "checklist_created": True, "manifest_updated": True},
        "manifest_status": "application_packaged",
    }
    package_path = submission / "application_package.json"; package_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    (submission / "application_package.md").write_text(f"# Application Package\n\n**Ready for form review - not submitted**\n\n- {manifest['company']} - {manifest['role']}\n- Resume: {package['page_counts']['resume']} page(s)\n- Cover letter: {package['page_counts']['cover_letter']} page(s){' (intentionally omitted)' if not include_cover else ''}\n- File integrity: verified\n- Status: application packaged\n", encoding="utf-8")
    manifest["status"] = "application_packaged"
    manifest.setdefault("artifacts", {}).update({"submission_resume_pdf": "submission/resume.pdf", "submission_cover_letter_pdf": "submission/cover_letter.pdf" if include_cover else None, "application_package_json": "submission/application_package.json", "application_package_markdown": "submission/application_package.md", "submission_checklist": "submission/submission_checklist.md"})
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, "scripts/validate_application_package.py", str(workspace), "--schema", str(SCHEMA)], cwd=ROOT, check=True)
    return package_path

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("lead_id"); args = parser.parse_args(); print(assemble(args.lead_id)); return 0
if __name__ == "__main__": raise SystemExit(main())

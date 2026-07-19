---
name: application-package-assembler
description: Assemble and validate a submission-ready job application package from finalized resume and cover-letter releases
version: 1.0.0
author: Anna Stupachenko
platforms: [macos, linux]
---

# Application Package Assembler

Assemble the approved resume and cover letter into a single immutable,
submission-ready package.

This workflow packages and validates only. It does not rewrite, revise, review,
render, rename source artifacts, or submit an application.

## Required Inputs

Application files:

- `applications/{company}-{role}/application_manifest.json`
- `applications/{company}-{role}/final_resume.md`
- `applications/{company}-{role}/final_resume.pdf`
- `applications/{company}-{role}/resume_finalization.json`
- `applications/{company}-{role}/resume_pdf_release.json`
- `applications/{company}-{role}/final_cover_letter.md`
- `applications/{company}-{role}/final_cover_letter.pdf`
- `applications/{company}-{role}/cover_letter_finalization.json`
- `applications/{company}-{role}/cover_letter_pdf_release.json`

## Outputs

Create:

```text
applications/{company}-{role}/submission/
    resume.pdf
    cover_letter.pdf
    application_package.json
    application_package.md
    submission_checklist.md
```

Update:

- `applications/{company}-{role}/application_manifest.json`

Set manifest status to:

`application_packaged`

The package JSON must conform to:

`${HERMES_SKILL_DIR}/references/application-package-schema.json`

## Preconditions

Packaging is permitted only when:

- manifest status is `cover_letter_rendered`;
- resume release status is `rendered`;
- cover letter release status is `cover_letter_rendered`;
- resume and cover letter belong to the same application ID;
- company and role match across all release artifacts;
- source PDF hashes match their release metadata;
- no existing submission package would be overwritten.

## Non-Negotiable Rules

1. Do not modify source PDFs.
2. Package copies must be byte-for-byte identical to source PDFs.
3. Do not silently overwrite an existing `submission/` directory.
4. Do not rename source files.
5. Use stable submission filenames:
   - `resume.pdf`
   - `cover_letter.pdf`
6. Record SHA256 hashes for source and packaged files.
7. Verify that the packaged files match their source releases.
8. Do not submit the application.
9. Do not browse.
10. Do not package draft, unreviewed, or stale artifacts.
11. Do not report readiness unless validation passes.

## Procedure

### 1. Validate release state

Confirm:

- manifest status;
- application ID consistency;
- company and role consistency;
- resume PDF release metadata;
- cover letter PDF release metadata;
- source PDF hashes;
- source PDF existence and readability.

### 2. Create submission directory

Create:

```text
applications/{company}-{role}/submission/
```

Stop if it already exists and contains files.

### 3. Copy release artifacts

Copy without modification:

```text
final_resume.pdf
→ submission/resume.pdf

final_cover_letter.pdf
→ submission/cover_letter.pdf
```

### 4. Create package metadata

Create `submission/application_package.json` containing:

- application ID;
- company;
- role;
- package version;
- creation timestamp in UTC;
- source artifacts;
- packaged artifacts;
- source and packaged hashes;
- page counts;
- release references;
- identity checks;
- submission readiness checks;
- manifest status.

### 5. Create package summary

Create `submission/application_package.md` with:

1. Package status
2. Application
3. Included documents
4. Release provenance
5. File integrity
6. Page counts
7. Submission readiness
8. Manifest status

### 6. Create submission checklist

Create `submission/submission_checklist.md` containing:

- employer and role verified;
- application URL verified;
- resume attached;
- cover letter attached when requested;
- filenames verified;
- form answers reviewed;
- salary response reviewed;
- work authorization response reviewed;
- voluntary demographic questions handled intentionally;
- final confirmation captured;
- submission timestamp recorded.

The checklist must remain unchecked because this workflow does not submit.

### 7. Update manifest

Set status to:

`application_packaged`

Add paths for:

- packaged resume;
- packaged cover letter;
- package JSON;
- package Markdown;
- submission checklist.

### 8. Validate

Run:

```bash
python3 scripts/validate_application_package.py \
  applications/{company}-{role}
```

Do not report completion unless validation passes.

## Return to Anna

Report:

- application;
- package path;
- package version;
- resume pages;
- cover letter pages;
- integrity result;
- manifest status;
- next step.

## Common Failure Modes

### Packaging stale PDFs

Always verify source hashes against release metadata.

### Overwriting an existing package

Submission packages are immutable. Stop instead.

### Copying draft files

Only final rendered PDFs are permitted.

### Marking checklist items complete

The assembler does not submit or verify form actions.

### Combining documents

Keep resume and cover letter as separate PDFs unless an employer explicitly
requires one combined file.

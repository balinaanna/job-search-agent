---
name: resume-pdf-renderer
description: Render a locked final resume Markdown file into a polished ATS-friendly PDF without changing approved content
version: 1.0.0
author: Anna Stupachenko
platforms: [macos, linux]
---

# Resume PDF Renderer

Convert an approved, locked `final_resume.md` into an ATS-friendly PDF.

This workflow controls presentation only. It must not rewrite, shorten, expand,
reorder, or otherwise change approved resume content.

## Required Inputs

Run from the root of `job-search-agent`.

Application files:

- `applications/{company}-{role}/application_manifest.json`
- `applications/{company}-{role}/final_resume.md`
- `applications/{company}-{role}/resume_finalization.json`
- `applications/{company}-{role}/resume_trace.json`

Renderer files:

- `scripts/render_resume_pdf.py`
- `scripts/validate_resume_pdf.py`

## Outputs

Create:

- `applications/{company}-{role}/final_resume.pdf`
- `applications/{company}-{role}/resume_pdf_release.json`
- `applications/{company}-{role}/resume_pdf_release.md`

Create an immutable snapshot:

- `applications/{company}-{role}/versions/final_resume_v{N}.pdf`

Update:

- `applications/{company}-{role}/application_manifest.json`

Set manifest status to:

`rendered`

The release JSON must conform to:

`${HERMES_SKILL_DIR}/references/resume-pdf-release-schema.json`

## Release Gate

Rendering is permitted only when:

- manifest status is `ready`;
- resume finalization validation passes;
- `final_resume.md` exists;
- source Markdown hash matches the finalization record;
- there are no unresolved finalization failures.

If any condition fails, stop.

## Non-Negotiable Rules

1. Do not alter approved wording.
2. Do not omit lines, bullets, headings, dates, contact details, or sections.
3. Do not add decorative content.
4. Do not add page headers, footers, watermarks, icons, columns, tables, or text boxes.
5. Use a single-column ATS-friendly layout.
6. Use embedded standard fonts only.
7. Avoid Unicode glyphs that commonly fail in PDF renderers.
8. Do not overwrite an existing versioned PDF.
9. Render and inspect the PDF before marking the workflow complete.
10. Do not mark the application submitted.
11. Do not browse.

## Default Presentation

Unless explicitly configured:

- US Letter page size;
- 0.55-inch side margins;
- 0.45-inch top and bottom margins;
- Helvetica font family;
- applicant name at 16 pt;
- contact line at 9 pt;
- section headings at 10.5 pt bold;
- body at 9.25 pt;
- compact bullet spacing;
- single-column flow;
- no photo;
- no graphics;
- no skill-rating bars;
- no color-dependent meaning.

The renderer may reduce body font to 8.75 pt or margins to 0.45 inches only
when needed to prevent an otherwise avoidable extra page. It must record the
effective settings.

## Procedure

### 1. Validate source release

Confirm:

- manifest status is `ready`;
- finalization JSON exists and validates;
- finalization manifest status is `ready`;
- source Markdown SHA-256 matches the finalization record;
- application IDs agree.

### 2. Determine PDF version

Read the final version from `resume_finalization.json`.

Use the same version number for:

- `versions/final_resume_v{N}.pdf`.

Refuse to overwrite an existing version.

### 3. Render

Run:

```bash
python3 scripts/render_resume_pdf.py \
  applications/{company}-{role}
```

The renderer must:

- parse the approved Markdown conservatively;
- preserve line order;
- preserve headings;
- preserve bullets;
- preserve inline emphasis as presentation only;
- create a single-column PDF;
- write `final_resume.pdf`;
- write the matching versioned PDF;
- write a preliminary release record.

### 4. Render PDF to images

Use the installed PDF verification tool:

```bash
python /home/oai/skills/pdfs/scripts/render_pdf.py \
  applications/{company}-{role}/final_resume.pdf \
  --out_dir applications/{company}-{role}/pdf_render_check \
  --dpi 180
```

Inspect every rendered page.

Reject the PDF if there is:

- clipped text;
- overlapping text;
- missing glyphs;
- black squares;
- malformed bullets;
- unexpectedly blank pages;
- nearly empty spillover pages;
- inconsistent margins;
- unreadably small text.

### 5. Validate textual fidelity

Run:

```bash
python3 scripts/validate_resume_pdf.py \
  applications/{company}-{role}
```

The validator checks:

- release schema;
- source and PDF hashes;
- application IDs;
- finalization version;
- output paths;
- PDF page count;
- extracted PDF text against normalized Markdown text;
- required headings and bullets;
- manifest status;
- versioned snapshot.

### 6. Complete release record

Record:

- application ID;
- final version;
- source Markdown path and hash;
- PDF paths and hashes;
- page count;
- renderer and font settings;
- text-fidelity result;
- visual inspection result;
- manifest status;
- next permitted workflows.

Create a readable Markdown summary.

### 7. Update manifest

Set status to:

`rendered`

Add or update artifact paths for:

- final PDF;
- PDF release JSON;
- PDF release Markdown.

Preserve all other metadata.

### 8. Clean verification artifacts

After successful inspection, remove `pdf_render_check/`.

Do not remove the final PDF, snapshot, release JSON, or release Markdown.

## Markdown Release Summary

1. PDF release result
2. Application
3. Final version
4. Source artifact
5. PDF artifacts
6. Page count
7. Layout settings
8. Text fidelity
9. Visual inspection
10. Manifest status
11. Next permitted workflows

## Return to Anna

Report:

- PDF version;
- page count;
- final PDF path;
- snapshot path;
- text-fidelity result;
- visual inspection result;
- manifest status;
- next step.

## Common Failure Modes

### Editing content to make it fit

Do not. Adjust typography within safe limits or report that a content revision
is needed.

### Using columns

Avoid them. They reduce parsing reliability.

### Trusting PDF generation without rendering

Always inspect rendered PNG pages.

### Treating text extraction as visual validation

Both extraction and image rendering are required.

### Leaving temporary renders in the application folder

Remove them after successful inspection.

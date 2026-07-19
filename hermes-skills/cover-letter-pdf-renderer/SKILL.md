---
name: cover-letter-pdf-renderer
description: Render a finalized cover letter to a validated, versioned PDF release
version: 1.0.0
author: Anna Stupachenko
platforms: [macos, linux]
---

# Cover Letter PDF Renderer

Render `final_cover_letter.md` into a professional PDF after finalization.

This workflow renders and verifies only. It does not rewrite, revise, review,
or finalize content.

## Required Inputs

- `applications/{company}-{role}/application_manifest.json`
- `applications/{company}-{role}/final_cover_letter.md`
- `applications/{company}-{role}/cover_letter_finalization.json`
- `applications/{company}-{role}/cover_letter_finalization.md`

## Outputs

Create:

- `applications/{company}-{role}/final_cover_letter.pdf`
- `applications/{company}-{role}/cover_letter_pdf_release.json`
- `applications/{company}-{role}/cover_letter_pdf_release.md`

Create a versioned immutable copy:

- `applications/{company}-{role}/versions/final_cover_letter_vN.pdf`

Update:

- `applications/{company}-{role}/application_manifest.json`

Set manifest status to:

`cover_letter_rendered`

The release JSON must conform to:

`${HERMES_SKILL_DIR}/references/cover-letter-pdf-release-schema.json`

## Preconditions

Rendering is permitted only when:

- manifest status is `cover_letter_ready`;
- cover letter finalization validation passed;
- final cover letter hash matches finalization metadata;
- all release-critical inputs exist.

## Non-Negotiable Rules

1. Do not change the letter content.
2. Do not add headers, footers, dates, addresses, or contact details unless they
   already exist in `final_cover_letter.md`.
3. Preserve paragraph order and text.
4. Use a professional one-page business-letter layout when the content fits.
5. Never shrink body text below 10 pt merely to force one page.
6. If two pages are required, use two pages rather than clipping or crowding.
7. Create the versioned PDF only after validation passes.
8. Render the PDF to PNG using the official PDF render script.
9. Inspect every rendered page.
10. Do not report success if clipping, overlap, broken glyphs, or black boxes are
    visible.
11. Use ASCII hyphens where generated metadata requires punctuation.
12. Record exact SHA256 hashes.

## Default Layout

- US Letter page size
- 0.8 inch left and right margins
- 0.75 inch top and bottom margins
- readable serif or sans-serif font
- 10.5-11 pt body text
- approximately 14-16 pt leading
- left aligned
- paragraph spacing instead of first-line indents
- no decorative graphics
- no page number on a one-page letter

## Procedure

### 1. Validate finalization

Confirm:

- manifest status;
- application ID consistency;
- source finalization verdict and score;
- final letter hash;
- finalization release checks.

### 2. Render PDF

Run:

```bash
python3 scripts/render_cover_letter_pdf.py \
  applications/{company}-{role}
```

### 3. Render pages to PNG

Run:

```bash
python /home/oai/skills/pdfs/scripts/render_pdf.py \
  applications/{company}-{role}/final_cover_letter.pdf \
  --out_dir applications/{company}-{role}/.cover_letter_pdf_render \
  --dpi 200
```

### 4. Inspect visually

Inspect every PNG and confirm:

- no clipping;
- no overlapping text;
- no broken glyphs;
- no black squares;
- consistent margins;
- readable type;
- clean paragraph spacing;
- balanced page composition.

### 5. Create release metadata

Create `cover_letter_pdf_release.json` containing:

- application ID;
- company and role;
- version;
- input and output paths;
- input, output, and versioned PDF hashes;
- page count;
- extracted text check;
- visual inspection record;
- release checks;
- manifest status.

### 6. Create versioned PDF

After validation, copy:

```text
final_cover_letter.pdf
→ versions/final_cover_letter_vN.pdf
```

Never overwrite an existing version.

### 7. Create release summary

Create `cover_letter_pdf_release.md`.

### 8. Update manifest

Set status to:

`cover_letter_rendered`

Add paths for:

- final PDF;
- versioned PDF;
- release JSON;
- release Markdown.

### 9. Validate

Run:

```bash
python3 scripts/validate_cover_letter_pdf.py \
  applications/{company}-{role}
```

## Return to Anna

Report:

- PDF path;
- version;
- page count;
- source and PDF hashes;
- extracted-text result;
- visual inspection result;
- manifest status.

## Common Failure Modes

### Reformatting content

Layout may change. Text may not.

### Forcing one page

Never sacrifice readability or clip text.

### Skipping visual inspection

Text extraction alone cannot detect layout defects.

### Creating version copy before validation

Only validated releases are versioned.

### Leaving render artifacts

Remove `.cover_letter_pdf_render/` after inspection.

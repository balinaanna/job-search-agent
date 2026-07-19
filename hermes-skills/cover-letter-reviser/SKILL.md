---
name: cover-letter-reviser
description: Apply only approved cover letter review findings while preserving strategy, evidence, paragraph structure, and version history
version: 1.0.0
author: Anna Stupachenko
platforms: [macos, linux]
---

# Cover Letter Reviser

Revise a drafted cover letter using only the approved findings in
`cover_letter_review.json`.

This workflow revises only. It does not re-plan, re-review, finalize, or render.

## Required Inputs

Application files:

- `applications/{company}-{role}/application_manifest.json`
- `applications/{company}-{role}/cover_letter_plan.json`
- `applications/{company}-{role}/cover_letter.md`
- `applications/{company}-{role}/cover_letter_trace.json`
- `applications/{company}-{role}/cover_letter_review.json`
- `applications/{company}-{role}/cover_letter_review.md`
- `applications/{company}-{role}/candidate_strategy.json`
- `applications/{company}-{role}/final_resume.md`
- `applications/{company}-{role}/resume_trace.json`

Profile files:

- `profile/evidence.yaml`
- `profile/forbidden_claims.yaml`
- `profile/writing_style.md`

## Outputs

Update:

- `applications/{company}-{role}/cover_letter.md`
- `applications/{company}-{role}/cover_letter_trace.json`
- `applications/{company}-{role}/application_manifest.json`

Create:

- `applications/{company}-{role}/cover_letter_revision.json`
- `applications/{company}-{role}/cover_letter_revision.md`

Create immutable snapshots before editing:

- `applications/{company}-{role}/versions/cover_letter_vN.md`
- `applications/{company}-{role}/versions/cover_letter_trace_vN.json`
- `applications/{company}-{role}/versions/cover_letter_review_vN.json`
- `applications/{company}-{role}/versions/cover_letter_review_vN.md`

Set manifest status to:

`cover_letter_revision`

The revision JSON must conform to:

`${HERMES_SKILL_DIR}/references/cover-letter-revision-schema.json`

## Preconditions

Revision is permitted only when:

- manifest status is `cover_letter_review`;
- review verdict is `minor_revision`, `major_revision`, or `rewrite_required`;
- review validation passed;
- review contains findings;
- revision brief authorizes at least one paragraph;
- all finding, paragraph, evidence, and resume element IDs resolve.

If verdict is `ready`, do not revise. Continue to Cover Letter Finalizer.

## Non-Negotiable Rules

1. Apply only findings listed in the review revision brief.
2. Edit only authorized paragraph IDs.
3. Preserve paragraph order and paragraph count.
4. Preserve all reviewer-identified strengths.
5. Do not add new evidence IDs.
6. Do not add new resume element IDs.
7. Do not invent claims, metrics, motivations, employer facts, or keywords.
8. Do not change the candidate strategy or cover letter plan.
9. Keep the revised letter within the planned word range.
10. Create version snapshots before any edit.
11. Record every material change.
12. Do not browse.
13. Do not re-score the letter.
14. Do not mark findings resolved unless the text actually addresses them.
15. Do not finalize or render.

## Revision Scope

For every finding in `revision_brief.priority_order`:

- locate the authorized paragraph;
- apply the exact revision instruction;
- stay within `evidence_boundaries`;
- preserve everything listed in `must_preserve`;
- avoid all prohibited changes;
- record the before and after text;
- record the change rationale;
- mark the finding as `resolved`, `partially_resolved`, or `not_resolved`.

No unlisted finding may be applied.

## Versioning

Before editing:

1. Create `versions/` if missing.
2. Find the next positive integer `N`.
3. Copy the current artifacts to:
   - `cover_letter_vN.md`
   - `cover_letter_trace_vN.json`
   - `cover_letter_review_vN.json`
   - `cover_letter_review_vN.md`
4. Record all snapshot paths and SHA256 hashes in the revision JSON.

Never overwrite an existing version snapshot.

## Procedure

### 1. Validate state

Confirm:

- manifest status;
- review verdict;
- application ID consistency;
- authorized paragraph IDs;
- finding priority order;
- evidence references;
- word range;
- current trace consistency.

### 2. Create snapshots

Create immutable version files before editing.

### 3. Revise authorized paragraphs

For each approved finding:

- use the exact paragraph ID;
- make the smallest sufficient change;
- preserve approved claims and evidence;
- keep keywords natural;
- avoid verbatim resume duplication;
- keep tone consistent with `writing_style.md`.

### 4. Update cover letter trace

For every revised paragraph update:

- final text;
- keywords used;
- word count;
- required claims status;
- prohibited content status.

Do not alter evidence IDs or resume element IDs unless the review explicitly
identifies an invalid reference and the plan already supports the correction.

### 5. Create revision report

Create `cover_letter_revision.json` with:

- application ID;
- source verdict and score;
- version number;
- snapshot paths and hashes;
- authorized paragraph IDs;
- processed findings;
- paragraph changes;
- unchanged paragraph IDs;
- before and after total word counts;
- evidence preservation checks;
- plan preservation checks;
- validation results;
- manifest status.

Create a readable `cover_letter_revision.md`.

### 6. Update manifest

Set status to:

`cover_letter_revision`

Add paths for:

- cover letter revision JSON;
- cover letter revision Markdown;
- latest cover letter;
- latest trace.

### 7. Validate

Run:

```bash
python3 scripts/validate_cover_letter_revision.py \
  applications/{company}-{role}
```

Do not report success unless validation passes.

## Markdown Structure

1. Revision summary
2. Source review
3. Version snapshot
4. Findings addressed
5. Paragraph changes
6. Preserved strengths
7. Evidence and strategy checks
8. Word-count check
9. Unresolved findings
10. Manifest status

## Return to Anna

Report:

- source score and verdict;
- version number;
- findings resolved;
- unresolved findings;
- paragraphs changed;
- before and after word counts;
- revision path;
- manifest status;
- next step.

## Common Failure Modes

### Rewriting the entire letter

Make the smallest sufficient edits.

### Applying unapproved improvements

Do not make changes that are not tied to an approved finding.

### Losing strong language

Reviewer-identified strengths are protected.

### Adding new evidence

Revision may improve expression, not expand the factual record.

### Overwriting history

Snapshots are mandatory and immutable.

### Self-reviewing after revision

The workflow validates mechanics and provenance only. It does not assign a new
quality score.

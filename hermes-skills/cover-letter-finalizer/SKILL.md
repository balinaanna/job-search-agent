---
name: cover-letter-finalizer
description: Finalize an approved cover letter after a ready review without changing its content
version: 1.0.0
author: Anna Stupachenko
platforms: [macos, linux]
---

# Cover Letter Finalizer

Finalize a cover letter only after the Cover Letter Reviewer returns `ready`.

This workflow freezes the approved cover letter. It does not rewrite, revise,
re-plan, review, or render.

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

Create:

- `applications/{company}-{role}/final_cover_letter.md`
- `applications/{company}-{role}/cover_letter_finalization.json`
- `applications/{company}-{role}/cover_letter_finalization.md`

Update:

- `applications/{company}-{role}/application_manifest.json`

Set manifest status to:

`cover_letter_ready`

The finalization JSON must conform to:

`${HERMES_SKILL_DIR}/references/cover-letter-finalization-schema.json`

## Preconditions

Finalization is permitted only when:

- manifest status is `cover_letter_review`;
- review verdict is `ready`;
- review score is at least 90;
- cover letter draft validation passed;
- review validation passed;
- no critical or high findings exist;
- revision brief authorizes no paragraph changes;
- all required files exist;
- application IDs agree.

If any precondition fails, stop without creating finalization artifacts.

## Non-Negotiable Rules

1. Do not change the cover letter text.
2. `final_cover_letter.md` must be byte-for-byte identical to `cover_letter.md`.
3. Do not add or remove greetings, closings, punctuation, whitespace, or metadata.
4. Do not resolve findings.
5. Do not create version snapshots.
6. Do not browse.
7. Do not render PDF or DOCX.
8. Do not mark the application ready unless all hashes and validations pass.
9. Record exact SHA256 hashes for all release inputs and outputs.
10. Preserve the review score and verdict exactly.

## Procedure

### 1. Validate state

Confirm:

- manifest status;
- review verdict and score;
- application ID consistency;
- review findings by severity;
- empty revision authorization;
- plan and trace consistency;
- current letter and trace existence.

### 2. Freeze the approved letter

Copy:

```text
cover_letter.md
→ final_cover_letter.md
```

The files must be byte-for-byte identical.

### 3. Create finalization metadata

Create `cover_letter_finalization.json` containing:

- application ID;
- company and role;
- source review score and verdict;
- source and final artifact paths;
- source and final SHA256 hashes;
- trace, plan, review, strategy, and resume hashes;
- paragraph count;
- total word count;
- target word range;
- evidence coverage;
- release checks;
- manifest status.

### 4. Create finalization summary

Create `cover_letter_finalization.md` with:

1. Release status
2. Application
3. Review approval
4. Final artifact
5. Content integrity
6. Word count
7. Evidence coverage
8. Release hashes
9. Manifest status
10. Next step

### 5. Update manifest

Set status to:

`cover_letter_ready`

Add artifact paths for:

- `final_cover_letter.md`
- `cover_letter_finalization.json`
- `cover_letter_finalization.md`

Preserve existing artifact paths.

### 6. Validate

Run:

```bash
python3 scripts/validate_cover_letter_finalization.py \
  applications/{company}-{role}
```

Do not report completion unless validation passes.

## Return to Anna

Report:

- score and verdict;
- final letter path;
- paragraph count;
- word count;
- content identity check;
- release hash;
- manifest status;
- next step.

## Common Failure Modes

### Polishing during finalization

Do not make any textual change.

### Finalizing a low-scoring ready review

Both verdict `ready` and score at least 90 are required.

### Finalizing with authorized revisions

A ready review must authorize no paragraph edits.

### Hashing only the final file

Hash all release-critical inputs.

### Rendering inside the finalizer

Rendering is a separate workflow.

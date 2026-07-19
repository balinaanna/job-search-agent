---
name: resume-finalizer
description: Finalize a reviewed resume only after a ready verdict and lock the approved content
version: 1.0.0
author: Anna Stupachenko
platforms: [macos, linux]
---

# Resume Finalizer

Finalize an approved resume without changing its content.

This workflow is a release gate. It does not edit, rewrite, improve, or restyle
the resume.

## Required Inputs

Run from the root of `job-search-agent`.

Application files:

- `applications/{company}-{role}/application_manifest.json`
- `applications/{company}-{role}/resume_plan.json`
- `applications/{company}-{role}/resume.md`
- `applications/{company}-{role}/resume_trace.json`
- `applications/{company}-{role}/resume_review.json`
- `applications/{company}-{role}/resume_review.md`

Profile files:

- `profile/career.yaml`
- `profile/skills.yaml`
- `profile/technologies.yaml`
- `profile/evidence.yaml`
- `profile/forbidden_claims.yaml`

## Outputs

Create:

- `applications/{company}-{role}/final_resume.md`
- `applications/{company}-{role}/resume_finalization.json`
- `applications/{company}-{role}/resume_finalization.md`

Create an immutable release snapshot:

- `applications/{company}-{role}/versions/final_resume_v{N}.md`
- `applications/{company}-{role}/versions/final_resume_trace_v{N}.json`
- `applications/{company}-{role}/versions/final_resume_review_v{N}.json`

Update:

- `applications/{company}-{role}/application_manifest.json`

Set manifest status to:

`ready`

The JSON must conform to:

`${HERMES_SKILL_DIR}/references/resume-finalization-schema.json`

## Release Gate

Finalization is permitted only when:

- manifest status is `review`;
- latest reviewer verdict is `ready`;
- latest review score is at least 90;
- critical finding count is zero;
- high finding count is zero;
- resume draft validation passes;
- resume review validation passes;
- no unresolved revision conflict remains;
- all required files exist.

If any condition fails, do not finalize.

## Non-Negotiable Rules

1. Do not alter resume wording.
2. Do not reorder sections or bullets.
3. Do not change punctuation, spacing, or Markdown structure.
4. Copy `resume.md` byte-for-byte to `final_resume.md`.
5. Preserve the exact approved trace and review in versioned snapshots.
6. Do not mark ready unless every release-gate condition passes.
7. Do not generate a PDF in this workflow.
8. Do not browse.
9. Do not overwrite an existing final version.
10. Record cryptographic hashes for the source and final files.

## Procedure

### 1. Validate current state

Confirm:

- application IDs agree across manifest, plan, trace, and review;
- manifest status is `review`;
- reviewer verdict is `ready`;
- score is at least 90;
- critical and high counts are zero;
- current resume and review validators pass;
- all paths resolve.

### 2. Determine final version

Create `versions/` if needed.

Find the next available integer version for:

- `final_resume_v{N}.md`;
- `final_resume_trace_v{N}.json`;
- `final_resume_review_v{N}.json`.

Never overwrite.

### 3. Compute source hashes

Compute SHA-256 hashes for:

- `resume.md`;
- `resume_trace.json`;
- `resume_review.json`;
- `resume_plan.json`.

### 4. Lock approved content

Copy `resume.md` byte-for-byte to:

- `final_resume.md`;
- `versions/final_resume_v{N}.md`.

Copy the current trace and review to the matching versioned paths.

After copying, compute SHA-256 for the final files.

The source resume hash and both final resume hashes must match.

### 5. Create finalization record

Create `resume_finalization.json` containing:

- application ID;
- final version number;
- reviewer score and verdict;
- source and output paths;
- file hashes;
- release-gate results;
- finalized timestamp;
- manifest status;
- next permitted workflows.

Create a readable Markdown summary.

### 6. Update manifest

Set status to `ready`.

Add or update artifact paths for:

- final resume Markdown;
- finalization JSON;
- finalization Markdown.

Preserve all other metadata.

### 7. Verify

Before responding:

- validate finalization JSON;
- confirm all gate checks are true;
- confirm hashes match;
- confirm final resume is byte-identical to source resume;
- confirm snapshots exist;
- confirm no snapshot was overwritten;
- confirm manifest status is `ready`;
- confirm all final files exist.

## Markdown Structure

1. Finalization result
2. Application
3. Approved review score
4. Final version
5. Locked artifacts
6. Hash verification
7. Release-gate checks
8. Manifest status
9. Next permitted workflows

## Return to Anna

Report:

- final version number;
- approved review score;
- final resume path;
- snapshot path;
- hash verification result;
- manifest status;
- next step.

## Common Failure Modes

### Making one last improvement

Do not. Finalization is not editing.

### Finalizing a minor-revision result

Only `ready` is accepted.

### Producing PDF too early

PDF rendering is a separate downstream workflow.

### Overwriting the approved version

Every release must be versioned and reversible.

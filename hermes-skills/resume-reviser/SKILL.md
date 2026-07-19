---
name: resume-reviser
description: Revise a resume using an approved recruiter review brief while preserving verified strengths
version: 1.0.0
author: Anna Stupachenko
platforms: [macos, linux]
---

# Resume Reviser

Apply the approved revision brief to an existing resume without reopening the entire strategy.

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
- `profile/writing_style.md`

## Outputs

Create versioned backups:

- `applications/{company}-{role}/versions/resume_v{N}.md`
- `applications/{company}-{role}/versions/resume_trace_v{N}.json`
- `applications/{company}-{role}/versions/resume_review_v{N}.json`
- `applications/{company}-{role}/versions/resume_review_v{N}.md`

Replace the working files:

- `applications/{company}-{role}/resume.md`
- `applications/{company}-{role}/resume_trace.json`

Create:

- `applications/{company}-{role}/resume_revision.json`
- `applications/{company}-{role}/resume_revision.md`

Update manifest status to:

`drafting`

The revision JSON must conform to:

`${HERMES_SKILL_DIR}/references/resume-revision-schema.json`

## Non-Negotiable Rules

1. Treat `resume_review.json` revision brief as the authorized change list.
2. Do not independently redesign the resume strategy.
3. Preserve all strengths marked `must_remain_unchanged` or `strengths_to_preserve`.
4. Revise only the listed sections, bullets, ordering, keywords, wording, and repetition.
5. Do not add new claims, evidence, metrics, skills, technologies, or keywords.
6. Every revised experience bullet must retain a valid planned bullet ID.
7. Evidence provenance must remain valid.
8. Do not change titles, dates, employers, degree names, or certification status.
9. Do not remove a critical role or project unless the review explicitly authorizes it.
10. Do not mark the resume ready.
11. Do not browse unless explicitly asked.
12. If review instructions conflict with the plan or evidence, preserve factual safety and record the conflict.

## Procedure

### 1. Validate the current state

Confirm:

- manifest status is `review`;
- resume review validates;
- resume and trace validate;
- review application ID matches plan and manifest;
- revision brief references real planned bullet IDs;
- current working files exist.

Stop on structural failure.

### 2. Create immutable backups

Create `versions/` if needed.

Determine the next integer version number.

Back up the current:

- resume;
- resume trace;
- review JSON;
- review Markdown.

Never overwrite an existing version.

### 3. Build authorized change set

Read:

- `sections_to_revise`;
- `planned_bullet_ids_to_revise`;
- `planned_bullet_ids_to_remove`;
- `planned_bullet_order`;
- `keywords_to_integrate`;
- `wording_to_soften`;
- `repetition_to_consolidate`;
- `must_remain_unchanged`;
- `strengths_to_preserve`.

For each review finding, classify it:

- applied;
- partially applied;
- not applied;
- conflict.

### 4. Revise sections

Apply only authorized changes.

For summary and skills:

- improve clarity or alignment only as directed;
- use only planned messages and items;
- preserve line and category limits.

For experience bullets:

- revise only authorized planned bullet IDs;
- remove only authorized IDs;
- reorder only where specified;
- preserve evidence and metrics constraints;
- do not merge bullets unless repetition consolidation explicitly requires it.

For projects, education, and certifications:

- change only if named in the review brief;
- preserve scope qualifiers and exact records.

### 5. Preserve strengths

Compare the revised draft against:

- `strengths_to_preserve`;
- `must_remain_unchanged`;
- unchanged trace elements.

If a required strength is weakened or removed, restore it.

### 6. Regenerate trace

Create a complete replacement `resume_trace.json`.

For every element include:

- final text;
- planned bullet ID;
- source and evidence IDs;
- keywords and metrics;
- constraints checked.

Also add revision metadata where supported by the trace:

- changed from previous version;
- related finding IDs.

If the existing trace schema does not permit extra fields, keep revision metadata only in `resume_revision.json`.

### 7. Create revision record

Create `resume_revision.json` with:

- application ID;
- revision number;
- source review path;
- backup paths;
- revised resume and trace paths;
- findings disposition;
- changed elements;
- removed planned bullet IDs;
- reordered planned bullet IDs;
- preserved elements;
- unresolved conflicts;
- before/after word counts;
- manifest status.

Create a readable Markdown version.

### 8. Update manifest

Set status to `drafting`.

Preserve all other metadata.

Do not delete review files. They remain the source for this revision cycle.

### 9. Verify

Before responding:

- validate revision JSON;
- validate revised resume and trace using the Resume Writer validator;
- confirm backups exist;
- confirm no backup was overwritten;
- confirm every critical and high finding has a disposition;
- confirm no unauthorized planned bullet changed;
- confirm removed bullets were authorized;
- confirm reordered bullets were authorized;
- confirm preserved strengths remain;
- confirm no new evidence, metrics, keywords, or source IDs appear;
- confirm manifest status is `drafting`;
- confirm all output files exist.

## Markdown Structure

1. Revision result
2. Source review and version
3. Changes applied
4. Findings disposition
5. Bullets revised, removed, or reordered
6. Strengths preserved
7. Conflicts or instructions not applied
8. Validation result
9. Next step

## Return to Anna

Report:

- revision number;
- revised resume path;
- backup path;
- number of findings applied;
- unresolved conflicts;
- manifest status;
- whether the resume should be reviewed again.

## Common Failure Modes

### Rewriting from scratch

Do not. This is a controlled revision pass.

### Applying every reviewer suggestion blindly

Evidence and plan constraints override unsafe suggestions.

### Losing strong content

Strength preservation is mandatory.

### Failing to version

Every revision cycle must be reversible.

### Marking ready too early

The revised resume returns to drafting and must go through review again.

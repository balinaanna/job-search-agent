---
name: cover-letter-reviewer
description: Review a drafted cover letter against its approved plan, evidence, and role strategy without rewriting it
version: 1.0.0
author: Anna Stupachenko
platforms: [macos, linux]
---

# Cover Letter Reviewer

Evaluate the drafted cover letter as a recruiter and hiring manager.

This workflow reviews only. It does not rewrite, revise, or re-plan.

## Required Inputs

- `applications/{company}-{role}/application_manifest.json`
- `applications/{company}-{role}/cover_letter_plan.json`
- `applications/{company}-{role}/cover_letter.md`
- `applications/{company}-{role}/cover_letter_trace.json`
- `applications/{company}-{role}/candidate_strategy.json`
- `applications/{company}-{role}/final_resume.md`
- `applications/{company}-{role}/resume_trace.json`
- `jobs/analyzed/{company}-exploration-{role}/analysis.json`
- `profile/evidence.yaml`
- `profile/forbidden_claims.yaml`
- `profile/writing_style.md`

## Outputs

Create:

- `applications/{company}-{role}/cover_letter_review.json`
- `applications/{company}-{role}/cover_letter_review.md`

Update the manifest status to:

`cover_letter_review`

The JSON must conform to:

`${HERMES_SKILL_DIR}/references/cover-letter-review-schema.json`

## Preconditions

Review is permitted only when:

- manifest status is `cover_letter_drafting`;
- draft validation passed;
- recommendation is `write` or `optional`;
- trace and plan IDs agree.

## Scoring

- Opening and first impression: 15
- Strategic alignment: 20
- Evidence and specificity: 25
- Employer relevance: 15
- Clarity and readability: 15
- Credibility and restraint: 10

## Verdicts

- 90–100: `ready`
- 80–89: `minor_revision`
- 65–79: `major_revision`
- below 65: `rewrite_required`

## Rules

1. Review only.
2. Do not rewrite.
3. Do not provide replacement sentences.
4. Every finding must identify a paragraph ID.
5. Every finding must explain impact.
6. Revision instructions must stay within approved evidence.
7. Preserve strengths explicitly.
8. Do not browse.
9. Update manifest only after validation passes.

## Finding Severity

- `critical`: unsupported or false claim, wrong employer or role, contradiction
- `high`: major strategic gap, weak evidence, generic motivation
- `medium`: clarity, repetition, structure, or keyword issue
- `low`: polish issue with limited impact

## Procedure

1. Validate application IDs, manifest status, paragraph order, word count, and trace.
2. Review opening and first impression.
3. Review strategy alignment.
4. Review evidence and specificity.
5. Review employer relevance.
6. Review clarity, restraint, repetition, and credibility.
7. Create strengths and findings.
8. Create a bounded revision brief.
9. Update manifest to `cover_letter_review`.
10. Run:

```bash
python3 scripts/validate_cover_letter_review.py   applications/{company}-{role}
```

## Return to Anna

Report score, verdict, strongest aspect, highest-priority issue, findings by
severity, review path, manifest status, and next step.

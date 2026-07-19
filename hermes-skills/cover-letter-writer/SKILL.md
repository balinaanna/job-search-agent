---
name: cover-letter-writer
description: Write a tailored cover letter from an approved cover letter plan without changing strategy or inventing claims
version: 1.0.0
author: Anna Stupachenko
platforms: [macos, linux]
---

# Cover Letter Writer

Write the cover letter exactly from the approved `cover_letter_plan.json`.

This workflow writes only. It does not re-plan, review, or revise.

## Required Inputs

Application files:

- `applications/{company}-{role}/application_manifest.json`
- `applications/{company}-{role}/cover_letter_plan.json`
- `applications/{company}-{role}/cover_letter_plan.md`
- `applications/{company}-{role}/candidate_strategy.json`
- `applications/{company}-{role}/final_resume.md`
- `applications/{company}-{role}/resume_trace.json`

Profile files:

- `profile/evidence.yaml`
- `profile/forbidden_claims.yaml`
- `profile/writing_style.md`

## Outputs

Create:

- `applications/{company}-{role}/cover_letter.md`
- `applications/{company}-{role}/cover_letter_trace.json`

Update:

- `applications/{company}-{role}/application_manifest.json`

Set manifest status to:

`cover_letter_drafting`

The trace JSON must conform to:

`${HERMES_SKILL_DIR}/references/cover-letter-trace-schema.json`

## Preconditions

Writing is permitted only when:

- manifest status is `cover_letter_planning`;
- plan recommendation is `write` or `optional`;
- plan validation passed;
- all planned evidence and resume element IDs resolve;
- required profile files exist.

When plan recommendation is `skip`, do not write a letter.

## Non-Negotiable Rules

1. Follow the plan exactly.
2. Do not change paragraph count or order.
3. Do not add new claims, metrics, employer facts, or motivations.
4. Do not remove required claims.
5. Do not exceed the approved word range.
6. Use only evidence and resume elements identified in the plan.
7. Preserve the approved employer-specific angle.
8. Do not repeat resume bullets verbatim unless explicitly allowed.
9. Do not use forbidden phrases or prohibited exaggerations.
10. Do not browse.
11. Do not review or revise your own output.
12. Do not generate PDF or DOCX.

## Writing Style

Use:

- simple, professional language;
- direct sentences;
- natural first-person voice;
- concrete evidence;
- restrained confidence;
- concise transitions;
- no inflated enthusiasm;
- no AI-sounding filler.

Avoid:

- “I am writing to apply”
- “I am thrilled”
- “I am passionate about”
- “I would be a perfect fit”
- “dynamic team”
- “fast-paced environment”
- “unique opportunity”
- “leverage my skills”
- “proven track record” unless explicitly supported
- em dashes unless present in approved style guidance

## Procedure

### 1. Validate state

Confirm:

- manifest status;
- plan recommendation;
- application ID consistency;
- paragraph IDs;
- evidence IDs;
- resume element IDs;
- word range;
- prohibited content.

### 2. Draft paragraph by paragraph

For each planned paragraph:

- use its exact purpose;
- include its required claim;
- use only approved evidence;
- include keywords naturally;
- obey repetition restrictions;
- avoid prohibited exaggerations.

### 3. Create the cover letter

Write `cover_letter.md`.

The body should contain only the letter content.

Default structure:

- greeting;
- four body paragraphs, or the exact planned count;
- concise closing;
- candidate name.

Do not add:

- internal notes;
- evidence IDs;
- strategy labels;
- word counts;
- Markdown headings inside the letter.

### 4. Create provenance trace

Create `cover_letter_trace.json`.

For each paragraph record:

- paragraph ID;
- final text;
- purpose;
- evidence IDs;
- resume element IDs;
- keywords used;
- required claims satisfied;
- prohibited content checked;
- word count.

Also record:

- total word count;
- paragraph count;
- recommendation;
- plan path;
- manifest status.

### 5. Update manifest

Set status to:

`cover_letter_drafting`

Add artifact paths for:

- cover letter Markdown;
- cover letter trace JSON.

### 6. Validate

Run:

```bash
python3 scripts/validate_cover_letter_draft.py \
  applications/{company}-{role}
```

Do not report completion unless validation passes.

## Return to Anna

Report:

- letter path;
- paragraph count;
- total word count;
- target word range;
- evidence coverage;
- manifest status;
- next step.

## Common Failure Modes

### Improving the plan

Do not. The planner already made those decisions.

### Adding generic enthusiasm

Every sentence must earn its place.

### Repeating the resume

Interpret evidence and connect it to the role.

### Adding employer details from memory

Use only employer facts already approved in the plan.

### Hiding unsupported claims in transitions

Transitions are still claims and must remain grounded.

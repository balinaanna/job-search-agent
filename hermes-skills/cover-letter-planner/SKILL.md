---
name: cover-letter-planner
description: Create a deterministic, evidence-backed cover letter plan from an approved application strategy and finalized resume
version: 1.0.0
author: Anna Stupachenko
platforms: [macos, linux]
---

# Cover Letter Planner

Create the strategic and structural plan for a tailored cover letter.

This workflow plans only. It does not write the finished cover letter.

## Required Inputs

Run from the root of `job-search-agent`.

Application files:

- `applications/{company}-{role}/application_manifest.json`
- `applications/{company}-{role}/candidate_strategy.json`
- `applications/{company}-{role}/resume_plan.json`
- `applications/{company}-{role}/final_resume.md`
- `applications/{company}-{role}/resume_trace.json`
- `applications/{company}-{role}/resume_pdf_release.json`

Job analysis files:

- `jobs/analyzed/{company}-exploration-{role}/analysis.json`

Profile files:

- `profile/career.yaml`
- `profile/skills.yaml`
- `profile/technologies.yaml`
- `profile/evidence.yaml`
- `profile/job_preferences.yaml`
- `profile/forbidden_claims.yaml`
- `profile/writing_style.md`

## Outputs

Create:

- `applications/{company}-{role}/cover_letter_plan.json`
- `applications/{company}-{role}/cover_letter_plan.md`

Update:

- `applications/{company}-{role}/application_manifest.json`

Set manifest status to:

`cover_letter_planning`

The JSON must conform to:

`${HERMES_SKILL_DIR}/references/cover-letter-plan-schema.json`

## Preconditions

Planning is permitted only when:

- manifest status is `rendered`;
- resume PDF release validation passed;
- final resume exists;
- candidate strategy exists;
- job analysis exists;
- application IDs agree;
- no forbidden claim is required to support the strategy.

## Responsibilities

The planner decides:

- whether a cover letter is strategically useful;
- the core message;
- opening approach;
- employer-specific motivation;
- evidence sequence;
- paragraph structure;
- which resume evidence to reinforce;
- which resume content not to repeat;
- keywords to include naturally;
- risks and prohibited claims;
- word-count target;
- writer instructions.

The planner does not:

- draft prose;
- invent metrics;
- invent employer facts;
- create new evidence;
- alter the resume;
- change the candidate strategy.

## Strategic Use Decision

Set `recommendation` to one of:

- `write`
- `optional`
- `skip`

Use `write` when:

- the application explicitly requests a cover letter;
- the role values communication, consulting, client service, coordination,
  leadership, or motivation;
- the candidate needs to explain a career transition or unusual fit;
- the letter can add evidence not obvious in the resume.

Use `optional` when:

- the letter may help but adds limited incremental value.

Use `skip` when:

- the employer explicitly says not to include one;
- the application does not accept one;
- a letter would only repeat the resume;
- no credible employer-specific motivation is available.

Even when recommendation is `skip`, produce a valid plan explaining why.

## Non-Negotiable Rules

1. Use only evidence available in profile and approved application artifacts.
2. Every planned claim must cite evidence IDs or approved strategy IDs.
3. Do not invent employer culture, products, growth, mission, or recent news.
4. Do not use generic enthusiasm unsupported by the application record.
5. Do not repeat the resume paragraph by paragraph.
6. Do not overstate years, seniority, leadership, ownership, or domain expertise.
7. Preserve the candidate strategy.
8. Keep the target letter concise.
9. Do not write the final cover letter.
10. Do not browse.

## Default Letter Architecture

Unless strategy requires otherwise:

1. Opening: role + strongest fit + specific motivation
2. Evidence paragraph: most relevant business/technical achievement
3. Evidence paragraph: people-facing or cross-functional value
4. Closing: concise value proposition and interest

Preferred target:

- 280 to 380 words
- 4 paragraphs
- no bullets
- no heading inside the letter body
- no generic “I am writing to apply”
- no repeated summary from the resume

## Procedure

### 1. Validate state

Confirm:

- manifest status is `rendered`;
- application IDs match;
- final PDF release passed;
- required profile files exist;
- source evidence IDs resolve;
- candidate strategy handoff exists.

### 2. Decide strategic value

Determine:

- recommendation;
- rationale;
- what the cover letter adds beyond the resume;
- what risk it addresses;
- what evidence it should foreground.

### 3. Define message architecture

Create:

- central thesis;
- employer motivation;
- candidate value proposition;
- opening strategy;
- paragraph sequence;
- closing strategy.

### 4. Map evidence

For every paragraph, specify:

- paragraph ID;
- purpose;
- planned claim;
- supporting evidence IDs;
- approved resume element IDs;
- target keywords;
- repetition restrictions;
- prohibited exaggerations.

### 5. Define writing controls

Specify:

- target word range;
- paragraph count;
- tone;
- sentence complexity;
- first-person usage;
- forbidden phrases;
- personalization limits;
- formatting rules.

### 6. Create writer handoff

The handoff must tell the writer:

- exact paragraph order;
- required claims;
- evidence boundaries;
- keywords to include;
- what not to repeat;
- what not to invent;
- when to stop.

### 7. Validate

Run:

```bash
python3 scripts/validate_cover_letter_plan.py \
  applications/{company}-{role}
```

Do not update manifest status unless validation passes.

## Markdown Structure

1. Recommendation
2. Strategic role of the letter
3. Core message
4. Employer motivation
5. Paragraph plan
6. Evidence map
7. Keyword plan
8. Repetition controls
9. Risk controls
10. Writer handoff

## Return to Anna

Report:

- recommendation;
- target word count;
- paragraph count;
- core message;
- strongest evidence;
- employer-specific angle;
- plan path;
- manifest status;
- next step.

## Common Failure Modes

### Writing the letter during planning

Do not. Produce instructions, not final prose.

### Generic employer praise

Only use facts already present in the job analysis or candidate strategy.

### Repeating the resume

The letter must interpret and connect evidence, not duplicate bullets.

### Unsupported transition story

Career-transition framing must remain factual and strategically necessary.

### Treating optional as mandatory

The plan must explicitly state when a cover letter adds little value.

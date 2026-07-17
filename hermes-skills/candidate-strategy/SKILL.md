---
name: candidate-strategy
description: Turn a validated job-fit analysis into a unified application strategy
version: 1.0.0
author: Anna Stupachenko
platforms: [macos, linux]
metadata:
  hermes:
    tags: [Career, Job Search, Resume, Cover Letter, Interview]
---

# Candidate Strategy

Create one application strategy that all downstream workflows can follow.

## Required input

Run from the root of `job-search-agent`.

Input:

`jobs/analyzed/{company}-exploration-{role}/analysis.json`

Required profile files:

- `profile/career.yaml`
- `profile/skills.yaml`
- `profile/technologies.yaml`
- `profile/evidence.yaml`
- `profile/interview_stories.yaml`
- `profile/job_preferences.yaml`
- `profile/forbidden_claims.yaml`
- `profile/writing_style.md`

## Outputs

Save:

- `jobs/analyzed/{company}-exploration-{role}/candidate_strategy.json`
- `jobs/analyzed/{company}-exploration-{role}/candidate_strategy.md`

The JSON must conform to:

`${HERMES_SKILL_DIR}/references/candidate-strategy-schema.json`

## Rules

1. Use the validated analysis as the source of truth.
2. Do not rescore the role.
3. Preserve the original recommendation and total score.
4. Use only verified profile records.
5. Never add unsupported keywords, tools, metrics, titles, authority, or years.
6. Distinguish direct evidence from transferable positioning.
7. Do not hide material gaps.
8. Do not treat project-context technologies as hands-on expertise.
9. Keep the strategy selective; remove irrelevant content.
10. Do not write a full resume, cover letter, or interview answer.
11. Do not browse unless Anna explicitly asks.

## Procedure

### 1. Validate the analysis

Confirm the analysis contains:

- recommendation;
- total score;
- hiring priorities;
- requirement map;
- selected evidence;
- gaps;
- hard-reject results.

Stop if it is invalid or internally contradictory.

### 2. Load profile records

Build lookup maps for:

- employment IDs;
- project IDs;
- skill IDs;
- technology IDs;
- evidence IDs;
- interview-story IDs.

Every referenced ID must exist.

### 3. Infer likely hiring-manager mindset

Write four to seven informed hypotheses based only on the analysis.

Focus on what the manager likely needs solved, such as:

- independent requirements clarification;
- customer or stakeholder communication;
- implementation reliability;
- process improvement;
- technical translation;
- domain knowledge;
- risk reduction.

Do not invent internal company problems.

### 4. Define candidate positioning

Produce:

- one positioning statement;
- three to five positioning pillars;
- one differentiator;
- one sentence explaining why Anna's career path makes sense for this role.

Avoid generic or inflated language.

### 5. Build keyword strategy

Classify job language as:

- `critical`;
- `high`;
- `supporting`;
- `do_not_force`.

For each term include:

- why it matters;
- verified supporting IDs;
- suggested placement.

Do not create an ATS score.

### 6. Build resume strategy

Define:

- target identity;
- summary focus;
- top skills;
- roles to expand, keep standard, shorten, or omit;
- projects to include, keep optional, or omit;
- evidence order;
- title-handling notes;
- content to remove or deemphasize;
- one-page or two-page recommendation.

For each role include:

- role ID;
- treatment;
- reason;
- evidence IDs;
- maximum bullets.

Do not write final bullets.

### 7. Build cover-letter strategy

Define:

- whether a letter is worthwhile;
- opening angle;
- up to three evidence examples;
- role connection;
- gap handling;
- what not to repeat.

Do not draft the letter.

### 8. Build application-answer strategy

Identify likely question categories.

For each include:

- recommended evidence or story IDs;
- central message;
- risks to avoid.

Do not pretend these are exact questions unless supplied.

### 9. Build interview strategy

Select three to six stories from `interview_stories.yaml`.

For each include:

- story ID;
- likely question types;
- why it fits;
- role-specific emphasis;
- what detail to keep concise.

Also include:

- likely interview concern;
- response strategy;
- facts to verify;
- questions Anna should ask.

### 10. Identify risks

Separate:

- screening;
- interview;
- credibility;
- logistics.

For each risk include severity and honest mitigation.

### 11. Create downstream handoffs

Create instructions for:

- resume;
- cover letter;
- application answers;
- interview preparation.

Each handoff must state what to emphasize, what to avoid, which IDs to use, and tone.

### 12. Verify and save

Before finishing:

- parse the JSON;
- validate it against the schema;
- confirm all referenced IDs exist;
- confirm score and recommendation match the source analysis;
- confirm both files exist;
- confirm no forbidden claim appears.

## Markdown order

1. Strategy headline
2. Original fit verdict
3. Hiring-manager mindset
4. Candidate positioning
5. Keyword priorities
6. Resume strategy
7. Cover-letter strategy
8. Application-answer strategy
9. Interview strategy
10. Risks and mitigation
11. Downstream handoffs

## Return to Anna

Report:

- strategy headline;
- top three positioning pillars;
- most important risk;
- paths to both files.

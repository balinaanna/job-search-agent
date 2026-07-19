---
name: resume-reviewer
description: Review a tailored resume against the job, strategy, and plan like a recruiter
version: 1.0.0
author: Anna Stupachenko
platforms: [macos, linux]
---

# Resume Reviewer

Evaluate whether the current resume is strong enough to earn an interview.

This workflow does not merely proofread. It reviews the draft against the job
analysis, candidate strategy, resume plan, and evidence trace.

## Required Inputs

Run from the root of `job-search-agent`.

Application files:

- `applications/{company}-{role}/application_manifest.json`
- `applications/{company}-{role}/resume_plan.json`
- `applications/{company}-{role}/resume.md`
- `applications/{company}-{role}/resume_trace.json`

Exploration files:

- `jobs/analyzed/{company}-exploration-{role}/analysis.json`
- `jobs/analyzed/{company}-exploration-{role}/candidate_strategy.json`

Profile files:

- `profile/career.yaml`
- `profile/skills.yaml`
- `profile/technologies.yaml`
- `profile/evidence.yaml`
- `profile/forbidden_claims.yaml`
- `profile/writing_style.md`

## Outputs

Create:

- `applications/{company}-{role}/resume_review.json`
- `applications/{company}-{role}/resume_review.md`

Update:

- `applications/{company}-{role}/application_manifest.json`

Set manifest status to:

`review`

The JSON must conform to:

`${HERMES_SKILL_DIR}/references/resume-review-schema.json`

## Review Standard

Answer this question:

> Would a recruiter or hiring manager be likely to interview Anna based on this resume?

Evaluate both:

- compliance with the plan;
- persuasive strength of the final resume.

## Non-Negotiable Rules

1. Treat the job analysis and candidate strategy as the source of truth for role fit.
2. Treat the resume plan as the source of truth for content strategy.
3. Treat the resume trace as the source of truth for provenance.
4. Do not rewrite the resume during this workflow.
5. Do not invent additional experience or evidence.
6. Do not penalize the resume for omitting content that the plan intentionally excluded.
7. Do penalize weak execution of planned content.
8. Distinguish critical problems from polish.
9. Do not create fake ATS scores.
10. Do not recommend keyword stuffing.
11. Do not browse unless explicitly asked.
12. Keep review comments concrete and actionable.

## Procedure

### 1. Validate the workspace

Confirm:

- manifest status is `drafting` or `review`;
- resume and trace exist;
- plan, trace, and manifest application IDs agree;
- exploration source paths agree;
- score and recommendation are preserved;
- resume draft validation has passed or can be reproduced.

Stop if the draft is structurally invalid.

### 2. Simulate the first recruiter scan

Review the top third of the resume as though spending 6–10 seconds.

Assess:

- target identity clarity;
- immediate role relevance;
- strongest evidence visibility;
- summary usefulness;
- skills prioritization;
- whether the first experience bullets reinforce the target role.

Record the likely first impression in one concise paragraph.

### 3. Evaluate strategic alignment

Compare the resume against:

- hiring-manager mindset;
- positioning pillars;
- critical and high keywords;
- resume strategy;
- strongest selected evidence;
- known application risks.

For each strategic requirement classify coverage as:

- strong;
- adequate;
- weak;
- missing;
- intentionally excluded.

### 4. Evaluate evidence strength

Check whether:

- strongest evidence appears early;
- outcomes are visible;
- metrics are used where verified;
- bullets show actions rather than responsibilities;
- transferable experience is framed honestly;
- each role contributes distinct value;
- weak or repetitive bullets consume space.

Do not ask for metrics where none are verified.

### 5. Evaluate readability and structure

Assess:

- section order;
- visual scanability in plain Markdown;
- bullet length;
- paragraph density;
- repetition;
- chronology;
- role balance;
- page-length fit;
- awkward phrasing;
- jargon;
- AI-style language;
- grammatical or punctuation issues.

### 6. Evaluate keyword coverage

Use only the keyword strategy and plan.

For every critical and high term classify:

- naturally present;
- present but weak;
- absent with support available;
- absent and unsupported;
- intentionally excluded.

Do not estimate a proprietary ATS score.

### 7. Evaluate credibility and interview defensibility

Check:

- title presentation;
- dates;
- scope;
- seniority;
- ownership;
- technologies;
- metrics;
- project framing;
- wording likely to trigger difficult interview questions.

Flag any statement that is technically supported but framed too aggressively.

### 8. Score the draft

Create a transparent review score out of 100:

- First-scan clarity: 15
- Strategic alignment: 20
- Evidence and accomplishments: 25
- Relevance and keyword coverage: 15
- Readability and structure: 15
- Credibility and defensibility: 10

This score measures resume execution, not candidate fit.

Verdict:

- 90–100: `ready`
- 80–89: `minor_revision`
- 65–79: `major_revision`
- below 65: `rewrite_required`

A resume cannot receive `ready` if any critical issue remains.

### 9. Create prioritized findings

Every finding must include:

- finding ID;
- severity: critical, high, medium, low;
- category;
- resume location;
- problem;
- why it matters;
- exact revision instruction;
- source plan or strategy IDs where relevant;
- whether the Resume Writer can fix it automatically.

Avoid vague feedback such as:

- "Make it stronger."
- "Improve the summary."
- "Add more impact."

### 10. Create revision brief

Produce a short revision brief for the Resume Writer containing:

- sections to revise;
- bullet IDs to revise;
- bullets to remove;
- bullets to reorder;
- keywords to integrate;
- wording to soften;
- repetition to consolidate;
- content that must remain unchanged;
- target outcome.

Do not write replacement bullets.

### 11. Identify strengths to preserve

List the strongest elements that must not be lost in revision.

This prevents the next writing pass from degrading good content.

### 12. Save and update manifest

Save:

- `resume_review.json`
- `resume_review.md`

Update manifest status to `review`.

Do not mark the application ready.

### 13. Verify

Before responding:

- validate review JSON against the schema;
- confirm score components total correctly;
- confirm verdict matches score and critical-issue rule;
- confirm every referenced planned bullet ID exists;
- confirm every finding ID is unique;
- confirm critical findings appear in the revision brief;
- confirm strengths and revision instructions do not contradict;
- confirm manifest status is `review`;
- confirm both review files exist.

## Markdown Structure

1. Review verdict
2. Resume execution score
3. Likely recruiter first impression
4. What is working
5. Critical and high-priority findings
6. Strategic coverage
7. Keyword coverage
8. Readability and credibility
9. Revision brief
10. Strengths to preserve

## Return to Anna

Report:

- review score and verdict;
- strongest aspect;
- most important issue;
- number of critical/high findings;
- review file paths;
- whether the draft should proceed to revision or finalization.

## Common Failure Modes

### Grammar-only review

The objective is interview probability, not proofreading alone.

### Rewriting inside the review

Provide precise instructions, not replacement resume content.

### Penalizing honest gaps

A resume cannot claim unsupported experience. Review positioning, not fantasy.

### Too many equal-priority comments

Prioritize the few changes that materially improve interview chances.

### Reopening settled strategy

Flag true strategy conflicts, but do not casually redesign the resume plan.

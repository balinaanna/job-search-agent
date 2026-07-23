---
name: resume-planner
description: Convert candidate strategy into an evidence-grounded resume plan
version: 1.0.0
author: Anna Stupachenko
platforms: [macos, linux]
---

# Resume Planner

Create an application workspace and a concrete resume plan without drafting the resume.

## Input

- `jobs/analyzed/{company}-exploration-{role}/analysis.json`
- `jobs/analyzed/{company}-exploration-{role}/candidate_strategy.json`
- all profile YAML files

## Output

Create:

- `applications/{company}-{role}/application_manifest.json`
- `applications/{company}-{role}/resume_plan.json`
- `applications/{company}-{role}/resume_plan.md`

If the workspace already represents another posting or a submitted application, append the current date.

## Rules

1. Preserve the fit score and recommendation.
2. Do not rescore or reanalyze the job.
3. Use only verified profile IDs and facts.
4. Every planned experience bullet must cite evidence.
5. Every technology must have verified context.
6. Use only official or approved title variants.
7. Preserve employment dates exactly.
8. Respect `forbidden_claims.yaml`.
9. Do not invent polished resume wording.
10. Do not hide material gaps.
11. Do not calculate an ATS score.
12. Do not browse unless explicitly asked.

## Procedure

### 1. Validate upstream artifacts

Confirm company, role, score, recommendation, evidence IDs, and exploration slug agree.

For `do_not_apply`, create a plan only when explicitly requested and mark it `practice_only`.

### 2. Create the application manifest

Use application slug `{company}-{role}` and status `planning`.

Record:

- application ID;
- company and role;
- creation date;
- source exploration slug;
- paths to analysis and strategy;
- fit score and recommendation;
- expected downstream artifact paths;
- empty submission metadata.

### 3. Choose resume format

Choose `one_page` or `two_pages` based on candidate strategy, relevant work history,
project needs, technical density, and recruiter readability.

### 4. Define target identity

Plan:

- headline;
- summary purpose;
- three to five messages;
- tone;
- claims to avoid.

Do not draft the final summary.

### 5. Plan section order and space

Use this fixed section order. Include or exclude each section based on relevance,
but never reorder the included sections:

1. header;
2. professional summary;
3. core skills;
4. education;
5. certifications;
6. professional experience;
7. selected projects;
8. additional information.

Within education and certifications, order entries most recent to oldest.

For each section specify purpose, space budget, required content, optional content,
and exclusions.

### 6. Plan the summary

Specify:

- opening identity;
- experience context;
- core value;
- role strengths;
- outcome theme;
- keywords to integrate;
- claims to avoid;
- maximum lines.

### 7. Plan skills

Use no more than five recruiter-readable categories.

For every selected skill or technology include:

- display label;
- verified record ID;
- priority;
- placement reason;
- supporting IDs.

Exclude low-relevance, duplicate, unsupported, or misleading items.

### 8. Plan experience

For every included role specify:

- role ID;
- official and display titles;
- title justification;
- organization;
- exact dates;
- treatment;
- bullet limit;
- entry purpose.

Every planned bullet must include:

- unique bullet ID;
- evidence IDs;
- competency;
- job priority;
- factual message;
- outcome;
- allowed metrics;
- allowed keywords;
- wording constraints;
- priority.

The factual message is a content instruction, not final resume prose.

### 9. Plan projects

Specify project ID, placement, reason, bullet limit, evidence, problem, allowed tools,
outcome, scope qualifiers, and prohibited exaggerations.

### 10. Plan education and certifications

Include verified records only. Do not change names or status.

### 11. Map keywords

Map critical and high-priority terms to exact resume locations with supporting IDs,
direct/transferable status, and wording guardrails.

Put unsupported terms in `excluded_keywords`.

### 12. Define exclusions

Record omitted roles, evidence, skills, technologies, compression rules, forbidden
claims, and facts requiring qualified wording.

### 13. Create writer handoff

Give the future Resume Writer exact files, section order, bullet limits, tone,
keyword rules, title/date/metric rules, prohibited content, and target length.

### 14. Save and verify

Validate `resume_plan.json` against:

`${HERMES_SKILL_DIR}/references/resume-plan-schema.json`

Validate the manifest against:

`${HERMES_SKILL_DIR}/references/application-manifest-schema.json`

Also verify:

- all IDs resolve;
- titles are approved;
- dates match career.yaml;
- each planned bullet has evidence;
- bullet IDs and section orders are unique;
- manifest paths are correct;
- all three files exist.

## Return

Report the workspace, target identity, resume length, emphasized roles, main
exclusion/risk, and paths to all generated files.

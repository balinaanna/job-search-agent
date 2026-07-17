---
name: job-fit-analyzer
description: Analyze job fit using verified candidate evidence
version: 1.0.0
author: Anna Stupachenko
platforms: [macos, linux]
metadata:
  hermes:
    tags: [Career, Job Search, Resume, Business Analysis]
---

# Job Fit Analyzer

Analyze a job description against Anna Stupachenko's verified profile.

## When to Use

Use this skill when Anna asks to:

- analyze a job posting;
- determine whether she should apply;
- score her fit;
- identify hiring priorities;
- map requirements to her experience;
- identify truthful resume positioning;
- identify gaps or application risks.

## Required Workspace

Run from the root of the `job-search-agent` project.

Required profile files:

- `profile/career.yaml`
- `profile/skills.yaml`
- `profile/technologies.yaml`
- `profile/evidence.yaml`
- `profile/job_preferences.yaml`
- `profile/forbidden_claims.yaml`
- `profile/writing_style.md`

The input should be either:

1. a path to a text or Markdown job description; or
2. pasted job-description text.

## Non-Negotiable Rules

1. Optimize for interview probability, not superficial keyword overlap.
2. Never invent experience, tools, metrics, certifications, authority, or years.
3. Treat `profile/forbidden_claims.yaml` as a hard constraint.
4. Use only evidence found in the profile files.
5. Distinguish:
   - direct evidence;
   - transferable evidence;
   - unsupported requirement.
6. Do not treat preferred qualifications as mandatory.
7. Distinguish screening requirements from trainable gaps.
8. Do not inflate project-context technology into hands-on expertise.
9. Preserve approximate wording for estimated metrics.
10. Reject a role when applying truthfully would require disguising a material gap.
11. Do not tailor or submit an application during this workflow.
12. Do not browse or research the company unless Anna explicitly asks.

## Procedure

### 1. Read the complete job description

Extract:

- job title;
- company;
- location;
- work arrangement;
- employment type;
- compensation, if provided;
- reporting relationship, if provided;
- mandatory requirements;
- preferred requirements;
- responsibilities;
- tools and technologies;
- industry or domain expectations;
- logistics such as driving, travel, schedule, and location.

Do not score the job before reading the entire posting.

### 2. Identify hiring priorities

Infer the five to eight most important hiring priorities.

Base priority on:

- repeated responsibilities;
- placement near the beginning;
- explicit words such as required, essential, must, key, primary, or core;
- percentage-of-time language;
- role purpose;
- screening questions;
- mandatory qualifications.

For each priority, assign:

- `critical`;
- `high`;
- `medium`;
- `low`.

### 3. Load verified candidate information

Read all required profile files.

Use:

- `career.yaml` for chronology and role context;
- `skills.yaml` for normalized skills;
- `technologies.yaml` for actual technology level;
- `evidence.yaml` for proof;
- `job_preferences.yaml` for logistics and target direction;
- `forbidden_claims.yaml` for restrictions;
- `writing_style.md` for natural wording.

### 4. Map every material requirement

For each material requirement, classify Anna's match:

- `direct`: directly supported by relevant evidence;
- `transferable`: supported by adjacent experience;
- `partial`: some relevant exposure, but not the requested depth;
- `unsupported`: no defensible evidence;
- `unknown`: the posting is unclear or the profile lacks enough detail.

Include:

- supporting evidence IDs;
- concise reasoning;
- risk level.

Never use a technology name as evidence by itself. Link it to a role, project,
skill, or evidence record.

### 5. Apply hard-reject rules

Check `job_preferences.yaml` and `forbidden_claims.yaml`.

Potential hard rejects include:

- mandatory personal vehicle or regular driving;
- mandatory licence or certification Anna does not hold;
- substantial direct people-management requirement;
- essential technology with no direct or transferable evidence;
- seniority that would require fabricated scope;
- incompatible location or travel;
- a role whose core work conflicts with Anna's stated direction.

A hard reject must be based on an explicit posting requirement, not speculation.

### 6. Calculate the fit score

Use the weights in `job_preferences.yaml`:

- responsibilities match: 35;
- evidence strength: 25;
- people-facing alignment: 15;
- technology match: 10;
- seniority match: 10;
- logistics match: 5.

Score each category from 0 to its maximum.

Scoring principles:

- Critical unsupported requirements reduce the score substantially.
- A preferred-tool gap should not outweigh strong responsibility evidence.
- Transferable evidence earns partial credit.
- Strong direct evidence for the core work matters more than keyword count.
- Apply a hard-reject override when appropriate.

Recommendation bands:

- `80-100`: strong apply;
- `65-79`: apply;
- `50-64`: selective/stretch apply;
- below `50`: do not apply.

A hard reject changes the recommendation to `do_not_apply` regardless of score.

### 7. Select resume evidence

Choose six to ten evidence items most useful for a tailored resume.

For each selected item provide:

- evidence ID;
- why it matters;
- recommended role placement;
- recommended bullet variant, if available.

Do not write the tailored resume yet.

### 8. Identify gaps and handling

Separate gaps into:

- `material_gaps`: could affect screening or performance;
- `trainable_gaps`: learnable tools or domain knowledge;
- `non_issues`: posting language that is already covered through different wording.

For each gap, state the honest handling:

- omit;
- address through transferable evidence;
- mention willingness to learn;
- clarify during screening;
- reject the role.

Never suggest hiding a material gap.

### 9. Save two outputs

Create a slug using lowercase company and role names.

Save:

`jobs/analyzed/<slug>/analysis.json`

and:

`jobs/analyzed/<slug>/analysis.md`

Create directories if needed.

The JSON must be valid and conform to
`${HERMES_SKILL_DIR}/references/analysis-schema.json`.

The Markdown report must be readable by Anna and include:

1. Verdict
2. Fit score
3. Why the role fits
4. Main risks
5. Hiring priorities
6. Requirement-to-evidence map
7. Best resume evidence
8. Gaps and honest handling
9. Recommended next action

### 10. Return a concise result

After saving the files, tell Anna:

- the recommendation;
- total score;
- the strongest three reasons;
- the most important risk;
- paths to both output files.

Do not produce a cover letter or tailored resume unless separately requested.

## Verification

Before finishing:

- parse `analysis.json` with Python's `json` module;
- confirm every cited evidence ID exists in `profile/evidence.yaml`;
- confirm category scores add to `total_score`;
- confirm the total is between 0 and 100;
- confirm no prohibited claim appears;
- confirm both output files exist.

If validation fails, correct the files before responding.

## Common Failure Modes

### Keyword scoring

Do not score based mainly on repeated keywords. Evaluate actual responsibilities
and evidence.

### Treating every requirement equally

Mandatory and core requirements matter more than optional tools.

### Over-crediting technical history

Past software-engineering experience is valuable, but it does not automatically
prove current specialist expertise in every technology.

### Ignoring logistics

Driving, location, travel, schedule, and work authorization affect fit.

### Writing the resume too early

This skill analyzes and selects evidence. Resume generation is a separate workflow.

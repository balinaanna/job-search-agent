---
name: resume-writer
description: Write a tailored resume from a validated resume plan
version: 1.0.0
author: Anna Stupachenko
platforms: [macos, linux]
---

# Resume Writer

Write a complete tailored resume from `resume_plan.json` without changing the upstream strategy.

## Inputs

- `applications/{company}-{role}/application_manifest.json`
- `applications/{company}-{role}/resume_plan.json`
- `applications/{company}-{role}/resume_plan.md`
- `profile/career.yaml`
- `profile/skills.yaml`
- `profile/technologies.yaml`
- `profile/evidence.yaml`
- `profile/forbidden_claims.yaml`
- `profile/writing_style.md`

## Outputs

Create:

- `applications/{company}-{role}/resume.md`
- `applications/{company}-{role}/resume_trace.json`

Update the manifest status to `drafting`.

## Rules

1. Treat `resume_plan.json` as the source of truth.
2. Do not rescore, replan, or silently change strategy.
3. Use only included sections, in planned order.
4. Respect role and project bullet limits.
5. Map every experience bullet to one planned bullet ID and its evidence IDs.
6. Preserve planned titles and exact dates.
7. Use only planned skills, technologies, keywords, education, and certifications.
8. Do not reintroduce excluded content.
9. Respect forbidden claims, scope qualifiers, and metric rules.
10. Keep writing natural, concise, ATS-friendly, and interview-defensible.
11. Do not use tables, columns, icons, ratings, graphics, or keyword stuffing.
12. Do not browse unless explicitly asked.

## Procedure

### Validate
Confirm manifest and plan IDs, company, role, score, recommendation, and artifact paths agree.

### Write
Create an ATS-friendly Markdown resume:

- verified header;
- professional summary from the summary plan;
- planned skills categories;
- professional experience using only planned bullets;
- included projects;
- education;
- certifications;
- any other planned section.

Every bullet should clearly state the action, context or problem, and verified outcome.

### Trace
Create `resume_trace.json`. For every generated element record:

- element ID;
- section and type;
- final text;
- planned bullet ID when applicable;
- source record IDs;
- evidence IDs;
- keywords used;
- metrics used;
- constraints checked.

### Update manifest
Set status to `drafting`. Do not mark ready or submitted.

### Verify
Before finishing:

- validate the trace schema;
- confirm section order;
- confirm each experience bullet maps to exactly one planned bullet;
- confirm no unplanned experience bullet exists;
- confirm bullet limits;
- confirm titles and dates;
- confirm only planned skills and keywords appear;
- confirm exclusions and forbidden claims are absent;
- confirm word count in the trace;
- confirm both files exist.

## Markdown format

```markdown
# Anna Stupachenko

Richmond, BC | phone | email | LinkedIn

## PROFESSIONAL SUMMARY

...

## SKILLS

**Category:** item, item

## PROFESSIONAL EXPERIENCE

### Display Title | Organization
Location | Month Year – Month Year

- Bullet

## SELECTED PROJECTS

### Project Name
- Bullet

## EDUCATION

...

## CERTIFICATIONS

...
```

## Return

Report resume path, trace path, word count, bullet counts, manifest status, and any plan instruction that could not be followed exactly.

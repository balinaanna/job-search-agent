# AI Job Search Agent

A user-friendly job-search tool designed to maximize the probability of
receiving relevant interviews. It discovers jobs, evaluates fit against a
verified career evidence library, builds an application strategy and tailored
package, and submits only after explicit user review and approval.

## Product workflow

`Discover → Analyze → Decide → Build → Review and approve → Apply → Track`

The Python workflow lives in `scripts/` and the product interface lives in
`ui/`. Generated job, analysis, and application records remain separate from
the immutable career evidence library in `profile/`.

## Current interface

Refresh its data from the repository root:

```bash
PYTHONPATH=scripts python3 scripts/export_dashboard_data.py
```

Then start it locally:

```bash
cd ui
npm run dev
```

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

In a second terminal, start the persistent workflow service:

```bash
PYTHONPATH=scripts python3 scripts/workflow_api.py
```

The Analyze action records an audited workflow run in `data/jobs.db`, starts an
ephemeral read-only Codex analysis, and validates the resulting artifact before
it can mark the analysis complete. `JOB_ANALYSIS_COMMAND` can override the
default worker with another approved command that accepts a lead ID and prints
the resulting `analysis.json` path.

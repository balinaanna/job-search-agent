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

## Initialize a private profile

Live career-profile YAML files are intentionally excluded from Git. After a
fresh clone, create private working copies from the sanitized templates:

```bash
python3 scripts/initialize_profile.py
```

This creates only missing files and never overwrites existing profile data.

## Safe capture mode

Automatic collection is deny-by-default. The agent never automates LinkedIn,
Indeed, or Eluta and never uses job-board credentials, cookies, or browser
sessions. It currently collects complete postings only through reviewed public
Greenhouse and Lever APIs. Unknown or blocked sources stay in the manual capture
queue. Redirects must remain on the approved allowlist, and access controls or
rate limits are never bypassed.

When an imported alert contains a direct link for a configured Greenhouse or
Lever account, the posting enters a locked background safe-capture queue. One
worker processes eligible postings sequentially, archives only complete job
descriptions, and leaves failures visible for review or retry. Job-board links
never enter this worker.

## Current interface

Refresh its data from the repository root:

```bash
PYTHONPATH=scripts python3 scripts/export_dashboard_data.py
```

Then start the complete application locally with one command:

```bash
python3 scripts/run_app.py
```

Open `http://localhost:3000`. The launcher starts both the interface and its
persistent workflow service. Press `Ctrl+C` to stop both.

For development, the two services can still be started separately:

```bash
PYTHONPATH=scripts python3 scripts/workflow_api.py
cd ui && npm run dev
```

The Analyze action records an audited workflow run in `data/jobs.db`, starts an
ephemeral read-only analysis, and validates the resulting artifact before it
can mark the analysis complete. By default this runs on Codex.

To switch between Codex and Claude Code without restarting the app, run:

```bash
python3 scripts/set_analysis_provider.py claude   # or: codex
```

This writes `data/analysis_provider.txt`, which `run_analysis_worker.py` reads
fresh on every run — the change applies to the very next Analyze click, no
restart needed. `JOB_ANALYSIS_PROVIDER` (env var) takes precedence over the
file if set, and `JOB_ANALYSIS_COMMAND` remains available as a full override
for another approved command that accepts a lead ID and prints the resulting
`analysis.json` path.

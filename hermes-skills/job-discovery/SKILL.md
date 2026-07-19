---
name: job-discovery
description: Collect, normalize, deduplicate, filter, and rank job opportunities against the candidate's Job Search Criteria contract.
---

# Job Discovery

Find opportunities that match the candidate's current strategy and convert them into canonical Job Lead artifacts.

## Canonical inputs

- `profile/career.yml`
- `strategy/job_search_criteria.json`

## Canonical contracts

- `references/job-lead-schema.json`
- `references/raw-job-posting-example.json`
- `references/job-lead-example.json`

## Runtime output

Normalized leads are written to:

`data/job-leads/`

Runtime leads are not committed to Git.

## Normalization

Normalize a raw job-posting JSON file with:

```bash
python3 scripts/normalize_job_lead.py path/to/raw-job-posting.json
```

## Deduplication

Run deduplication after new leads are normalized:

```bash
PYTHONPATH=scripts python3 scripts/deduplicate_job_leads.py
```

## Hard filtering

Apply the candidate's deterministic eligibility rules after deduplication and
before preliminary scoring:

```bash
PYTHONPATH=scripts python3 scripts/filter_job_leads.py
```

Confirmed hard failures are rejected. Missing information that prevents a safe
eligibility decision is marked for manual review rather than guessed.

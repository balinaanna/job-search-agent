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

## Public ATS collection

Copy the source configuration template and replace its examples with verified
employer board identifiers:

```bash
cp strategy/job_sources.example.json strategy/job_sources.json
```

Collect published postings from the configured public Greenhouse and Lever
feeds:

```bash
PYTHONPATH=scripts python3 scripts/collect_job_postings.py
```

Preview collection without writing files:

```bash
PYTHONPATH=scripts python3 scripts/collect_job_postings.py --dry-run
```

Raw postings are written to `data/raw-job-postings/`. Collection uses only
public read endpoints. It must not submit applications or access candidate
data. Employer names and board identifiers must be verified before they are
added to the active source configuration.

## End-to-end discovery run

Run the configured public collection sources through the complete discovery
pipeline and write the ranked shortlist:

```bash
PYTHONPATH=scripts python3 scripts/run_job_discovery.py
```

To process raw postings already on disk without network access:

```bash
PYTHONPATH=scripts python3 scripts/run_job_discovery.py --skip-collection
```

Repeated runs refresh posting content and timestamps while preserving review,
analysis, application, closed, and archived workflow states. An in-progress or
applied record remains canonical when the same job appears through another
source.

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

## Preliminary scoring and ranking

Score eligible and manual-review leads after hard filtering:

```bash
PYTHONPATH=scripts python3 scripts/score_job_leads.py
```

The scorer populates all seven discovery score components, applies configured
penalties, calculates the weighted preliminary score, and prints leads in rank
order. Only hard-filter passes at or above the full-analysis threshold are
recommended for Job Fit Analysis.

## Shortlist surfacing

After scoring, render a human-readable shortlist without modifying Job Lead
records:

```bash
PYTHONPATH=scripts python3 scripts/surface_job_leads.py \
  --output data/job-leads/shortlist.md
```

The report separates leads recommended for full Job Fit Analysis from leads
that need manual eligibility review, discovery-only leads, rejected leads,
unprocessed leads, and archived duplicates. Recommendations remain gated by
the hard filter and the configured full-analysis score threshold.

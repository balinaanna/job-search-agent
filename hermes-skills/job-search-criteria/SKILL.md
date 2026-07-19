---
name: job-search-criteria
description: Create, review, or update the candidate's durable Job Search Criteria contract. Use when career direction, target roles, technical priorities, locations, employment preferences, exclusions, hard filters, or discovery-ranking priorities change.
---

# Job Search Criteria

Maintain the candidate's durable job-search strategy.

## Canonical artifacts

Read and update:

- `profile/career.yml`
- `strategy/job_search_criteria.json`

Generate:

- `strategy/job_search_criteria.md`

Validate with:

```bash
python3 scripts/validate_job_search_criteria.py
```

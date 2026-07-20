# Job Search Agent interface

This is the user-facing workspace for the Job Search Agent. It presents the
real discovery and fit-analysis pipeline as a clear sequence of decisions:

1. discover and analyze jobs;
2. choose which opportunities to pursue;
3. build tailored application materials;
4. review and explicitly approve the package;
5. submit and track the application.

The interface currently consumes `app/dashboard-data.json`, generated from the
project's verified local workflow data:

```bash
PYTHONPATH=scripts python3 scripts/export_dashboard_data.py
```

Run the complete application from the repository root with
`python3 scripts/run_app.py`. For interface-only development, run `npm run dev`
from this directory. Validate a production build and rendered content with
`npm test`.

No application submission action belongs in the interface without an explicit
approval gate.

# Screenshots for the portfolio README

These images were captured with headless Chrome and pixelated
programmatically before being committed:

| File | Screen | Redaction |
|---|---|---|
| `overview.png` | Overview dashboard (`/`), top portion | None needed. No company/role names or contact info are visible above the job list. |
| `jobs.png` | Jobs workspace, scrolled to the job list | Each card's role title, company/location line, and avatar are pixelated. Everything else (workflow stage, fit score, dates, source) is untouched. |
| `profile.png` | Career profile → Skills tab | The header with contact info isn't in frame; the shot starts at the Skills section. |
| `workflow.png` | A job's "Open workflow" panel mid-pipeline: fit score, reasoning, the generated application strategy summary, and the 6-stage stepper caught live on "Resume Plan Running" | The role title and company name are pixelated (in the header and in the metadata grid). The reasoning text still mentions Anna's own city and past employers (Dooly, Techery) as evidence sources — that's her own public professional history, not the target company's, so it was left as-is. |

To regenerate any of these after a UI change, re-run the capture: launch
headless Chrome with `--remote-debugging-port`, connect over the DevTools
protocol, grab `getBoundingClientRect()` for the relevant elements, then
pixelate those rectangles with Pillow before saving. Selectors used so far:

- Jobs list: `.job-result header h3`, `.job-result header p`, `.company-avatar`
- Career profile header (if a shot ever includes it): `.master-resume header small`
- Workflow panel: `.job-workflow-detail header h3`, `.job-workflow-detail header p`,
  and the `<dd>` following the `<dt>Company</dt>` in `.workflow-job-overview dl`

Don't commit an unredacted screenshot while iterating.

# Demo script (~2–3 minute walkthrough)

A narration script for a screen recording (Loom or similar) to embed in your
portfolio alongside the README. Each beat names the screen, what to click,
and what to say. Keep total runtime under 3 minutes — reviewers skim.

Before recording: close any tab/panel that shows your phone number, email,
or candid "why you might not get this job" analysis text you don't want
public. None of that needs to be on screen for this script.

## 1. Hook (5–10s, no screen yet or a static title card)

> "This is a job-search platform I built that treats AI-generated resume
> claims the way a lint rule treats code — if a claim can't trace back to
> verified evidence, it doesn't ship."

## 2. Overview dashboard (~20s)

Screen: `/` (Overview)

- Point at the stats row: Discovered / Fully analyzed / Ready to pursue.
- Say: "It pulls in job leads from a browser extension and a couple of
  allow-listed public ATS APIs, then runs each one through an evidence-based
  fit analysis."

## 3. Jobs workspace + filters (~20s)

Screen: `/#jobs`

- Show the source filter dropdown (LinkedIn, Indeed, Eluta, ZipRecruiter,
  Greenhouse, Lever).
- Say: "Every source funnels into one workflow. Capture is always
  manual and user-initiated for the job boards themselves — this never
  automates logins or scrapes past bot protection."

## 4. Fit analysis on one job (~30s)

Screen: open a job card with a positive or neutral recommendation (avoid one
with harsh personal-gap commentary if you're camera-shy about it)

- Point at the score breakdown and the "strongest reasons" / "main risk"
  text.
- Say: "The analysis isn't keyword matching — it's scored against a
  structured library of verified accomplishments, and every reason it gives
  cites specific evidence, not a vibe."

## 5. Candidate strategy → resume pipeline (~30s)

Screen: Applications workspace, or a job's workflow panel showing
Strategy → Resume Plan → Draft → Review stages

- Say: "Once I decide to pursue something, it builds a strategy, then a
  resume plan, then drafts and reviews the actual document — each stage is
  its own schema-validated AI skill, so a bad output in one step can't
  quietly corrupt the next one."

## 6. Career profile / evidence library (~20s)

Screen: `/profile#skills` (crop out the contact-info line before/while
recording, or scroll past it)

- Say: "Everything downstream points back to this: a versioned, evidence-
  backed career record. If I update it, any stale analysis gets flagged for
  re-review automatically."

## 7. Close (~10s)

- Say: "It's a personal tool — SQLite, a Python backend, a React frontend,
  and a small Chrome extension for capture — but the interesting part isn't
  the CRUD, it's the guardrails: evidence traceability, human approval gates
  on anything consequential, and a safe-capture policy that treats job-board
  bot protection as a hard constraint, not an obstacle."

---

**Recording tips:**

- 1280×800 browser window keeps text legible without cropping.
- Trim dead air between clicks in editing rather than narrating live —
  scripted narration recorded separately over a silent screen capture reads
  more polished than live talk-and-click.
- Export as an MP4 or GIF and either upload to Loom (free tier) or commit a
  short GIF to `docs/screenshots/` and embed it at the top of the README.

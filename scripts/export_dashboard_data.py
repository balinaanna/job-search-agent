#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from surface_fit_queue import join_results, load_leads, load_valid_analyses


def job_record(result: Any) -> dict[str, Any]:
    lead = result.lead
    analysis = result.analysis
    return {
        "id": lead["lead_id"],
        "company": lead["identity"]["company"],
        "role": lead["identity"]["role"],
        "location": lead["location"].get("raw"),
        "postingUrl": lead["source"]["posting_url"],
        "postedDate": lead["application"].get("posted_date"),
        "firstSeenAt": lead["source"].get("first_seen_at") or lead["source"].get("collected_at"),
        "discoveryScore": lead["discovery"].get("preliminary_score"),
        "fitScore": analysis["score"]["total_score"],
        "recommendation": analysis["recommendation"],
        "reasons": analysis["summary"]["strongest_reasons"][:3],
        "risk": analysis["summary"]["main_risk"],
        "nextAction": analysis["summary"]["recommended_next_action"],
    }


def awaiting_record(lead: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": lead["lead_id"],
        "company": lead["identity"]["company"],
        "role": lead["identity"]["role"],
        "location": lead["location"].get("raw"),
        "postingUrl": lead["source"]["posting_url"],
        "postedDate": lead["application"].get("posted_date"),
        "firstSeenAt": lead["source"].get("first_seen_at") or lead["source"].get("collected_at"),
        "discoveryScore": lead["discovery"].get("preliminary_score"),
    }


def build_dashboard_data(
    leads_directory: Path,
    analyses_directory: Path,
    evidence_path: Path,
) -> dict[str, Any]:
    leads = [
        lead
        for lead in load_leads(leads_directory)
        if urlparse(lead["source"]["posting_url"]).hostname != "example.com"
    ]
    analyses = load_valid_analyses(analyses_directory, evidence_path)
    results, awaiting = join_results(leads, analyses)
    jobs = [job_record(result) for result in results]
    apply_count = sum(
        job["recommendation"] in {"strong_apply", "apply"} for job in jobs
    )
    stretch_count = sum(
        job["recommendation"] == "selective_apply" for job in jobs
    )
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "discovered": len(
                [lead for lead in leads if lead["status"]["lead_status"] != "archived"]
            ),
            "awaitingAnalysis": len(awaiting),
            "readyToPursue": apply_count,
            "stretch": stretch_count,
            "applicationsInProgress": sum(
                lead["status"]["lead_status"] == "application_started"
                for lead in leads
            ),
        },
        "analyzedJobs": jobs,
        "awaitingAnalysis": [awaiting_record(lead) for lead in awaiting],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the job workflow into dashboard-ready JSON."
    )
    parser.add_argument("--leads", type=Path, default=Path("data/job-leads"))
    parser.add_argument("--analyses", type=Path, default=Path("jobs/analyzed"))
    parser.add_argument("--evidence", type=Path, default=Path("profile/evidence.yaml"))
    parser.add_argument(
        "--output", type=Path, default=Path("ui/app/dashboard-data.json")
    )
    args = parser.parse_args()
    data = build_dashboard_data(args.leads, args.analyses, args.evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Exported dashboard data to {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

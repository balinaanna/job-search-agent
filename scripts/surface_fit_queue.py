#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from score_job_leads import normalized_text
from validate_job_analysis import (
    collect_referenced_ids,
    load_evidence_ids,
    load_json as load_analysis,
    validate_recommendation,
    validate_scores,
)
from validate_job_lead import JobLeadValidationError, load_json


DEFAULT_LEADS_DIRECTORY = Path("data/job-leads")
DEFAULT_ANALYSES_DIRECTORY = Path("jobs/analyzed")
DEFAULT_EVIDENCE_PATH = Path("profile/evidence.yaml")
DEFAULT_OUTPUT_PATH = Path("data/job-leads/action-queue.md")


@dataclass(frozen=True)
class FitResult:
    lead: dict[str, Any]
    analysis: dict[str, Any]
    analysis_path: Path


def identity_key(company: str, title: str) -> tuple[str, str]:
    return normalized_text(company), normalized_text(title)


def lead_identity(lead: dict[str, Any]) -> tuple[str, str]:
    return identity_key(lead["identity"]["company"], lead["identity"]["role"])


def analysis_identity(analysis: dict[str, Any]) -> tuple[str, str]:
    job = analysis["job"]
    return identity_key(job["company"], job["title"])


def load_leads(directory: Path) -> list[dict[str, Any]]:
    if not directory.exists():
        raise JobLeadValidationError(f"Leads directory does not exist: {directory}")
    return [load_json(path) for path in sorted(directory.glob("*.json"))]


def load_valid_analyses(
    directory: Path,
    evidence_path: Path,
    allow_stale_evidence: bool = False,
) -> list[tuple[Path, dict[str, Any]]]:
    if not directory.exists():
        return []

    evidence_ids = load_evidence_ids(evidence_path)
    results: list[tuple[Path, dict[str, Any]]] = []
    errors: list[str] = []
    for path in sorted(directory.glob("*/analysis.json")):
        try:
            analysis = load_analysis(path)
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
            continue
        analysis_errors = validate_scores(analysis)
        analysis_errors.extend(validate_recommendation(analysis))
        unknown = sorted(collect_referenced_ids(analysis) - evidence_ids)
        if unknown and not allow_stale_evidence:
            analysis_errors.append("Unknown evidence IDs: " + ", ".join(unknown))
        errors.extend(f"{path}: {error}" for error in analysis_errors)
        if not analysis_errors:
            results.append((path, analysis))

    if errors:
        raise JobLeadValidationError("Invalid fit analysis:\n" + "\n".join(errors))
    return results


def join_results(
    leads: list[dict[str, Any]],
    analyses: list[tuple[Path, dict[str, Any]]],
) -> tuple[list[FitResult], list[dict[str, Any]]]:
    by_source = {
        lead["source"]["posting_url"]: lead
        for lead in leads
        if lead["source"].get("posting_url")
    }
    by_identity = {lead_identity(lead): lead for lead in leads}
    matched_ids: set[str] = set()
    latest_by_lead: dict[str, tuple[tuple[int, int, int], FitResult]] = {}

    for index, (path, analysis) in enumerate(analyses):
        source = analysis["job"].get("source")
        lead = by_source.get(source) if source else None
        if lead is None:
            lead = by_identity.get(analysis_identity(analysis))
        if lead is None:
            continue
        lead_id = lead["lead_id"]
        matched_ids.add(lead_id)
        canonical = int(path.parent.name == lead_id)
        modified = path.stat().st_mtime_ns if path.exists() else 0
        rank = (canonical, modified, index)
        candidate = FitResult(lead, analysis, path)
        if lead_id not in latest_by_lead or rank > latest_by_lead[lead_id][0]:
            latest_by_lead[lead_id] = (rank, candidate)

    results = [value[1] for value in latest_by_lead.values()]

    awaiting = [
        lead
        for lead in leads
        if lead["lead_id"] not in matched_ids
        and lead["status"]["lead_status"] != "archived"
        and lead["discovery"].get("full_analysis_recommended") is True
    ]
    results.sort(
        key=lambda item: (
            -item.analysis["score"]["total_score"],
            item.lead["identity"]["normalized_company"],
            item.lead["identity"]["normalized_role"],
        )
    )
    awaiting.sort(
        key=lambda lead: (
            -(lead["discovery"].get("preliminary_score") or 0),
            lead["identity"]["normalized_company"],
            lead["identity"]["normalized_role"],
        )
    )
    return results, awaiting


def render_result(result: FitResult, rank: int) -> list[str]:
    lead = result.lead
    analysis = result.analysis
    final_score = analysis["score"]["total_score"]
    discovery_score = lead["discovery"].get("preliminary_score")
    delta = final_score - discovery_score if discovery_score is not None else None
    delta_label = f"; adjustment {delta:+d}" if delta is not None else ""
    reasons = analysis["summary"]["strongest_reasons"][:3]
    lines = [
        f"{rank}. **{lead['identity']['role']} — {lead['identity']['company']}** — {final_score}/100",
        f"   - Discovery score: {discovery_score if discovery_score is not None else 'not scored'}{delta_label}",
        f"   - Posting: {lead['source']['posting_url']}",
    ]
    lines.extend(f"   - Fit: {reason}" for reason in reasons)
    lines.append(f"   - Main risk: {analysis['summary']['main_risk']}")
    lines.append(
        f"   - Next action: {analysis['summary']['recommended_next_action']}"
    )
    return lines


def render_awaiting(lead: dict[str, Any], rank: int) -> list[str]:
    return [
        f"{rank}. **{lead['identity']['role']} — {lead['identity']['company']}** — preliminary {lead['discovery']['preliminary_score']}/100",
        f"   - Posting: {lead['source']['posting_url']}",
        "   - Next action: complete evidence-based fit analysis before considering an application.",
    ]


SECTION_LABELS = {
    "strong_apply": "Strong Apply",
    "apply": "Apply",
    "selective_apply": "Selective or Stretch Apply",
    "do_not_apply": "Do Not Apply",
}


def render_queue(results: list[FitResult], awaiting: list[dict[str, Any]]) -> str:
    buckets = {name: [] for name in SECTION_LABELS}
    for result in results:
        buckets[result.analysis["recommendation"]].append(result)
    counts = Counter(result.analysis["recommendation"] for result in results)
    lines = [
        "# Evidence-Based Job Action Queue",
        "",
        "Full fit scores supersede preliminary discovery scores. Applications should be prepared from the Apply sections, not from the discovery shortlist alone.",
        "",
        "## Summary",
        "",
        f"- Completed fit analyses: {len(results)}",
        f"- Strong apply: {counts['strong_apply']}",
        f"- Apply: {counts['apply']}",
        f"- Selective or stretch apply: {counts['selective_apply']}",
        f"- Do not apply: {counts['do_not_apply']}",
        f"- Awaiting full analysis: {len(awaiting)}",
    ]

    for name, heading in SECTION_LABELS.items():
        lines.extend(["", f"## {heading}", ""])
        if not buckets[name]:
            lines.append("None.")
            continue
        for rank, result in enumerate(buckets[name], start=1):
            lines.extend(render_result(result, rank))
            lines.append("")
        lines.pop()

    lines.extend(["", "## Awaiting Evidence-Based Analysis", ""])
    if not awaiting:
        lines.append("None.")
    else:
        for rank, lead in enumerate(awaiting, start=1):
            lines.extend(render_awaiting(lead, rank))
            lines.append("")
        lines.pop()
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine discovery leads and full fit analyses into an action queue."
    )
    parser.add_argument("--leads-directory", type=Path, default=DEFAULT_LEADS_DIRECTORY)
    parser.add_argument("--analyses-directory", type=Path, default=DEFAULT_ANALYSES_DIRECTORY)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        leads = load_leads(args.leads_directory)
        analyses = load_valid_analyses(args.analyses_directory, args.evidence)
        results, awaiting = join_results(leads, analyses)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_queue(results, awaiting), encoding="utf-8")
        print(f"Wrote evidence-based action queue to {args.output}.")
        print(f"Completed analyses: {len(results)}; awaiting: {len(awaiting)}.")
        return 0
    except (JobLeadValidationError, ValueError) as exc:
        print(f"Action queue generation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

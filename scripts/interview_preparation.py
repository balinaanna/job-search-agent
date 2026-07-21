from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


def build_interview_preparation(lead: dict, analysis: dict, strategy: dict, story_library: dict) -> dict:
    stories_by_id = {story["id"]: story for story in story_library.get("stories", [])}
    selected = []
    for choice in strategy["interview_strategy"]["selected_stories"]:
        story = stories_by_id.get(choice["story_id"])
        if not story:
            raise ValueError(f"Verified interview story not found: {choice['story_id']}")
        selected.append({**choice, "evidence_id": story["evidence_id"], "core_message": story["core_message"], "star": story["star"], "lesson": story["lesson"], "sample_questions": story["best_for"]})
    return {"schema_version": "1.0", "lead_id": lead["lead_id"], "company": lead["identity"]["company"], "title": lead["position"]["title"], "generated_at": datetime.now(timezone.utc).isoformat(), "posting": {"captured_at": lead["source"]["collected_at"], "original_url": lead["source"]["posting_url"]}, "hiring_priorities": analysis.get("hiring_priorities", [])[:5], "stories": selected, "most_likely_concern": strategy["interview_strategy"]["most_likely_concern"], "response_strategy": strategy["interview_strategy"]["response_strategy"], "verify_before_interview": strategy["interview_strategy"]["verify_before_interview"], "questions_to_ask": strategy["interview_strategy"]["questions_to_ask"]}


def prepare_for_lead(root: Path, lead_id: str) -> tuple[dict, Path]:
    lead = json.loads((root / "data/job-leads" / f"{lead_id}.json").read_text())
    analysis_dir = root / "jobs/analyzed" / lead_id
    analysis = json.loads((analysis_dir / "analysis.json").read_text())
    strategy = json.loads((analysis_dir / "candidate_strategy.json").read_text())
    stories = yaml.safe_load((root / "profile/interview_stories.yaml").read_text())
    package = build_interview_preparation(lead, analysis, strategy, stories)
    output = analysis_dir / "interview_preparation.json"; output.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n")
    return package, output

from __future__ import annotations

import json
import sys

from profile_rebuild_store import ProfileRebuildStore
from rebuild_profile_with_codex import ROOT, apply_profile_rebuild, prepare_profile_rebuild


def main() -> int:
    run_id = sys.argv[1]
    store = ProfileRebuildStore(ROOT / "data/jobs.db")
    run = store.get(run_id)
    selection = json.loads((ROOT / "data/profile-rebuilds" / run_id / "selection.json").read_text())
    items = (run.get("summary") or {}).get("review_items", [])
    selected = [items[index] for index in selection]
    rejected = [item for index, item in enumerate(items) if index not in selection]
    try:
        if rejected:
            files = [ROOT / "data/profile-rebuilds" / run_id / "uploads" / name for name in run["files"]]
            choice_rules = (
                "The user reviewed the proposed facts. Implement ONLY these approved changes:\n"
                + "\n".join(f"- {item['action']} {item['category']}: {item['fact']}" for item in selected)
                + "\nDo NOT implement these rejected changes:\n"
                + "\n".join(f"- {item['action']} {item['category']}: {item['fact']}" for item in rejected)
                + "\nMake only structural adjustments strictly required to keep the approved profile internally valid."
            )
            revised = prepare_profile_rebuild(run_id, files, f"{run['instructions']}\n\n{choice_rules}")
        else:
            revised = run["summary"]
        applied = apply_profile_rebuild(run_id, run["before_version"])
        store.update(run_id, "completed", summary={**revised, **applied}, after_version=applied["profile_version"])
        return 0
    except Exception as exc:
        store.update(run_id, "proposal_ready", summary=run.get("summary"), error=str(exc)[-4000:])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

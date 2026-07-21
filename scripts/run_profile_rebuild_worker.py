from __future__ import annotations

import sys
from pathlib import Path

from profile_rebuild_store import ProfileRebuildStore
from rebuild_profile_with_codex import ROOT, prepare_profile_rebuild


def main() -> int:
    run_id = sys.argv[1]
    store = ProfileRebuildStore(ROOT / "data/jobs.db")
    run = store.update(run_id, "running")
    files = [ROOT / "data/profile-rebuilds" / run_id / "uploads" / name for name in run["files"]]
    try:
        summary = prepare_profile_rebuild(run_id, files, run["instructions"])
        store.update(run_id, "proposal_ready", summary=summary)
        return 0
    except Exception as exc:
        store.update(run_id, "failed", error=str(exc)[-4000:])
        return 1


if __name__ == "__main__": raise SystemExit(main())

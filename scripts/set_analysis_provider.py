#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROVIDER_FILE = ROOT / "data/analysis_provider.txt"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Switch which AI provider the job-analysis worker uses."
    )
    parser.add_argument("provider", choices=["codex", "claude"])
    args = parser.parse_args()
    PROVIDER_FILE.write_text(args.provider + "\n", encoding="utf-8")
    print(f"Job analysis will now use: {args.provider}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile"
TEMPLATES = PROFILE / "templates"


def initialize_profile() -> list[Path]:
    """Create missing private profile files without overwriting user data."""
    created: list[Path] = []
    for template in sorted(TEMPLATES.glob("*.yaml")):
        destination = PROFILE / template.name
        if destination.exists():
            continue
        shutil.copyfile(template, destination)
        created.append(destination)
    return created


if __name__ == "__main__":
    paths = initialize_profile()
    if paths:
        for path in paths:
            print(f"Created {path.relative_to(ROOT)}")
    else:
        print("Profile already initialized; no files changed.")

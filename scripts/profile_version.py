from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROFILE_FILES = ("career.yaml", "skills.yaml", "technologies.yaml", "evidence.yaml")


def profile_version(profile_directory: Path) -> str:
    digest = hashlib.sha256()
    for name in PROFILE_FILES:
        path = profile_directory / name
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def analysis_profile_version(analysis_directory: Path) -> str | None:
    path = analysis_directory / "analysis_metadata.json"
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    version = value.get("profile_version")
    return version if isinstance(version, str) else None

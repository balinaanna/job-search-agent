#!/usr/bin/env python3

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    environment = os.environ.copy()
    python_path = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{ROOT / 'scripts'}{os.pathsep}{python_path}"
        if python_path
        else str(ROOT / "scripts")
    )
    processes = [
        subprocess.Popen(
            [sys.executable, "scripts/workflow_api.py"], cwd=ROOT, env=environment
        ),
        subprocess.Popen(["npm", "run", "dev"], cwd=ROOT / "ui", env=environment),
    ]

    def stop(*_: object) -> None:
        for process in processes:
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    print("Job Search Agent: http://localhost:3000")
    print("Press Ctrl+C to stop.")

    try:
        while all(process.poll() is None for process in processes):
            time.sleep(0.25)
    finally:
        stop()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    failed = [process.returncode for process in processes if process.returncode]
    return failed[0] if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Open key artifacts from the latest DoomArena-Lab run."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

from latest_run import ensure_latest

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_NAMES = ("summary.svg", "summary.csv")


def _open_with_default_app(path: Path) -> None:
    system = platform.system().lower()
    if system == "darwin":
        subprocess.run(["open", str(path)], check=False)
    elif system == "windows":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def main() -> int:
    run_info = ensure_latest(os.environ.get("RUN_ID"), update=True)
    if run_info is None:
        print("No run directories with summary artifacts were found.", file=sys.stderr)
        return 1

    run_dir = run_info.path
    rel_run = run_dir.relative_to(REPO_ROOT)
    print(f"Opening artifacts from {rel_run}")

    opened = False
    for name in ARTIFACT_NAMES:
        artifact = run_dir / name
        if artifact.exists():
            print(f" - {artifact.relative_to(REPO_ROOT)}")
            try:
                _open_with_default_app(artifact)
            except Exception as exc:  # pragma: no cover - best effort logging
                print(f"   ! Failed to open {artifact.name}: {exc}", file=sys.stderr)
            else:
                opened = True
        else:
            print(f" - Missing {name}; skipping.")

    if not opened:
        print("No artifacts could be opened.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

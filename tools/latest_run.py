#!/usr/bin/env python3
"""Utilities for discovering and updating the results/LATEST symlink."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "results"
LATEST_LINK = RESULTS_DIR / "LATEST"
SUMMARY_FILES = ("summary.csv", "summary.svg")


@dataclass
class RunInfo:
    path: Path
    mtime: float

    @property
    def run_id(self) -> str:
        return self.path.name


def _iter_candidate_runs(base: Path) -> Iterable[RunInfo]:
    if not base.exists():
        return []
    runs: list[RunInfo] = []
    for child in sorted(base.iterdir()):
        if child.name == "LATEST":
            continue
        if not child.is_dir():
            continue
        if not all((child / name).exists() for name in SUMMARY_FILES):
            continue
        try:
            mtime = max((child / name).stat().st_mtime for name in SUMMARY_FILES)
        except FileNotFoundError:
            continue
        runs.append(RunInfo(path=child, mtime=mtime))
    return runs


def _select_latest_run(base: Path) -> Optional[RunInfo]:
    candidates = list(_iter_candidate_runs(base))
    if not candidates:
        return None
    candidates.sort(key=lambda info: info.mtime, reverse=True)
    return candidates[0]


def _desired_run(run_id: Optional[str]) -> Optional[RunInfo]:
    if run_id:
        run_dir = RESULTS_DIR / run_id
        if run_dir.is_dir():
            mtimes = []
            for name in SUMMARY_FILES:
                artifact = run_dir / name
                try:
                    mtimes.append(artifact.stat().st_mtime)
                except FileNotFoundError:
                    continue
            try:
                mtime = max(mtimes)
            except ValueError:
                try:
                    mtime = run_dir.stat().st_mtime
                except FileNotFoundError:
                    return None
            return RunInfo(path=run_dir, mtime=mtime)
    return _select_latest_run(RESULTS_DIR)


def ensure_latest(run_id: Optional[str] = None, *, update: bool = True) -> Optional[RunInfo]:
    """Return the run used for LATEST and optionally update the symlink."""

    run = _desired_run(run_id)
    if run is None:
        return None

    if update:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        target = run.path
        try:
            if LATEST_LINK.is_symlink() or LATEST_LINK.exists():
                if LATEST_LINK.is_symlink() or LATEST_LINK.is_file():
                    LATEST_LINK.unlink()
                elif LATEST_LINK.is_dir():
                    shutil.rmtree(LATEST_LINK)
        except FileNotFoundError:
            pass

        try:
            LATEST_LINK.symlink_to(target)
        except OSError:
            # Fallback for platforms without symlink support: write a pointer file.
            with LATEST_LINK.open("w", encoding="utf-8") as fh:
                fh.write(str(target.resolve()))
    return run


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Update results/LATEST to the newest run.")
    parser.add_argument("--run-id", help="Specific run ID to mark as latest", default=None)
    parser.add_argument(
        "--show-only",
        action="store_true",
        help="Only display the resolved run without modifying results/LATEST.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    run_id_env = os.environ.get("RUN_ID")
    run = ensure_latest(args.run_id or run_id_env, update=not args.show_only)

    if run is None:
        print("No runs with summary.csv and summary.svg were found under results/", file=sys.stderr)
        return 0

    rel_path = run.path.relative_to(REPO_ROOT)
    action = "Resolved" if args.show_only else "Updated"
    print(f"{action} results/LATEST → {rel_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

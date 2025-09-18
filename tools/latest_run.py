#!/usr/bin/env python3
"""Utility helpers for maintaining the results/LATEST marker.

The helper serves two purposes:
1. Publishing a run directory as the latest results (creates/refreshes a
   symlink at ``results/LATEST``).
2. Printing the currently published run identifier (compatible with the
   previous ``cat results/LATEST`` behaviour).

Usage examples::

    # Print the currently published run ID (falls back to a friendly message
    # if nothing has been published yet).
    python tools/latest_run.py

    # Publish results/20240101-000000 as the latest run.
    python tools/latest_run.py --run-dir results/20240101-000000 \
        --run-id 20240101-000000 --require
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_RESULTS_ROOT = "results"
LATEST_NAME = "LATEST"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        help=(
            "Run directory to publish as latest. The path may be either "
            "absolute or relative to the repository root. If the directory "
            "is missing and --require is not supplied, the helper simply "
            "prints the currently published run."
        ),
    )
    parser.add_argument(
        "--run-id",
        help=(
            "Explicit run identifier to print after publishing. Defaults to "
            "the basename of --run-dir when provided."
        ),
    )
    parser.add_argument(
        "--results-root",
        default=DEFAULT_RESULTS_ROOT,
        help="Directory containing the published results (default: %(default)s)",
    )
    parser.add_argument(
        "--require",
        action="store_true",
        help=(
            "Treat a missing --run-dir as an error (exits with status 1). "
            "Useful when wiring publication steps such as `make report`."
        ),
    )
    return parser.parse_args()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _normalise_run_dir(repo: Path, raw: str | None) -> Path | None:
    if not raw:
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = (repo / raw).resolve()
    return candidate


def _current_run_id(marker: Path) -> str | None:
    """Return the run identifier currently advertised by ``marker``."""
    if marker.is_symlink():
        try:
            target = marker.resolve(strict=False)
            if target.exists():
                return target.name
        except OSError:
            pass
        try:
            # Fall back to the symlink payload, even if dangling.
            return Path(os.readlink(marker)).name
        except OSError:
            return None
    if marker.is_file():
        try:
            return marker.read_text(encoding="utf-8").strip()
        except OSError:
            return None
    return None


def _publish(marker: Path, run_dir: Path, run_id: str) -> None:
    marker.parent.mkdir(parents=True, exist_ok=True)
    # Remove any existing marker (file or symlink) before re-creating it.
    try:
        if marker.exists() or marker.is_symlink():
            marker.unlink()
    except OSError as exc:
        print(f"Failed to remove existing marker: {exc}", file=sys.stderr)
        raise
    # Use a relative symlink when possible to keep paths tidy inside the repo.
    try:
        rel_target = run_dir.relative_to(marker.parent)
    except ValueError:
        rel_target = run_dir
    marker.symlink_to(rel_target)
    print(run_id)


def main() -> int:
    args = _parse_args()
    repo = _repo_root()
    results_root = (repo / args.results_root).resolve()
    marker = results_root / LATEST_NAME

    run_dir = _normalise_run_dir(repo, args.run_dir)

    if run_dir is not None and run_dir.exists():
        run_id = args.run_id or run_dir.name
        _publish(marker, run_dir, run_id)
        return 0

    if run_dir is not None and args.require:
        print(f"Run directory '{run_dir}' not found.", file=sys.stderr)
        return 1

    # Fallback: print the currently published run identifier (if any).
    current = _current_run_id(marker)
    if current:
        print(current)
    else:
        print("No published run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Maintain a stable pointer to the newest valid results run.

Usage (positional args to match the Makefile):
    python tools/latest_run.py [RESULTS_ROOT] [LATEST_LINK]

Default RESULTS_ROOT = "results"
Default LATEST_LINK  = RESULTS_ROOT / "LATEST"

A "valid" run dir contains both `summary.csv` and `summary.svg`.
If symlinks aren’t supported, we write a fallback pointer file `results/LATEST.path`.
"""
from __future__ import annotations
import sys, pathlib

def is_valid_run(d: pathlib.Path) -> bool:
    return (d / "summary.csv").exists() and (d / "summary.svg").exists()

def newest_run(results: pathlib.Path) -> pathlib.Path | None:
    if not results.exists():
        return None
    cands = [p for p in results.iterdir() if p.is_dir() and p.name != "LATEST"]
    cands = [p for p in cands if is_valid_run(p)]
    if not cands:
        return None
    cands.sort(key=lambda p: p.stat().st_mtime)
    return cands[-1]

def main() -> int:
    results = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "results").resolve()
    link = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else results / "LATEST")
    run = newest_run(results)
    if not run:
        print(f"No valid run found under {results} (need summary.csv and summary.svg).")
        return 1

    # Remove existing link/file (but don't nuke a real directory named LATEST)
    if link.exists() or link.is_symlink():
        try:
            if link.is_symlink() or link.is_file():
                link.unlink()
        except Exception:
            pass

    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(run, target_is_directory=True)
        print(f"UPDATED: {link} -> {run}")
    except Exception as e:
        # Fallback pointer file if symlink creation fails
        pointer = link.parent / "LATEST.path"
        pointer.write_text(str(run), encoding="utf-8")
        print(f"Symlink failed ({e}); wrote {pointer} -> {run}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
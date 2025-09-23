#!/usr/bin/env python3
"""Open or print the latest DoomArena-Lab HTML report."""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path


def _as_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_pointer(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.exists():
        return resolved
    pointer = path.parent / f"{path.name}.path"
    if pointer.exists():
        target_text = pointer.read_text(encoding="utf-8").strip()
        if target_text:
            target = Path(target_text)
            if target.exists():
                try:
                    return target.resolve()
                except Exception:
                    return target
    return resolved


def _resolve_index(target: Path) -> Path:
    if target.is_dir():
        run_dir = _resolve_pointer(target)
        return run_dir / "index.html"
    if target.suffix.lower() == ".html":
        if target.exists():
            return target.resolve()
        run_dir = _resolve_pointer(target.parent)
        return run_dir / target.name
    run_dir = _resolve_pointer(target)
    return run_dir / "index.html"


def open_report(path: Path, *, print_only: bool) -> int:
    index_path = _resolve_index(path)
    if not index_path.exists():
        print(f"No report found at {index_path}", file=sys.stderr)
        return 1
    try:
        absolute = index_path.resolve()
    except Exception:
        absolute = index_path.absolute()
    print(absolute)
    if print_only:
        return 0
    try:
        opened = webbrowser.open(absolute.as_uri(), new=0, autoraise=True)
    except Exception as exc:
        print(f"WARNING: failed to open browser: {exc}", file=sys.stderr)
        return 0
    if not opened:
        print("NOTE: browser open returned False; path printed above.", file=sys.stderr)
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Open the latest HTML report in a browser")
    parser.add_argument(
        "target",
        nargs="?",
        default="results/LATEST",
        help="Report directory or index.html path (default: results/LATEST)",
    )
    args = parser.parse_args(argv)
    target_path = Path(args.target).expanduser()
    print_only = _as_bool(os.getenv("CI")) or _as_bool(os.getenv("MVP_PRINT_ONLY"))
    return open_report(target_path, print_only=print_only)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

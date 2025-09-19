#!/usr/bin/env python3
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path

def can_run(cmd: str) -> bool:
    from shutil import which
    return which(cmd) is not None

def try_open(p: Path) -> None:
    # Best-effort open for local dev; ignore errors in headless CI
    if sys.platform == "darwin" and can_run("open"):
        subprocess.Popen(["open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif sys.platform.startswith("linux") and can_run("xdg-open"):
        subprocess.Popen(["xdg-open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results/LATEST", help="results directory (default: results/LATEST)")
    ap.add_argument("--open", action="store_true", help="attempt to open files instead of just printing paths")
    ap.add_argument("--strict", action="store_true", help="exit non-zero if artifacts are missing")
    args = ap.parse_args(argv)

    root = Path(args.results)
    svg = root / "summary.svg"
    csvp = root / "summary.csv"

    if not root.exists():
        msg = f"[open-artifacts] No results to open: '{root}' does not exist. Run `make report` or `make demo` first."
        print(msg)
        return 1 if args.strict else 0

    found_any = False
    for p in (svg, csvp):
        if p.exists():
            found_any = True
            print(f"[open-artifacts] {p.resolve()}")
            if args.open:
                try_open(p)
        else:
            print(f"[open-artifacts] missing: {p}")

    if not found_any:
        return 1 if args.strict else 0
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

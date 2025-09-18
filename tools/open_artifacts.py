#!/usr/bin/env python3
import pathlib
import subprocess
import platform
from typing import Optional

def opener_cmd():
    s = platform.system().lower()
    if "darwin" in s:
        return ["open"]
    if "linux" in s:
        return ["xdg-open"]
    # On Windows, just print paths (GitHub runners often lack 'start' in non-interactive)
    return None

def resolve_latest(base_results: pathlib.Path) -> Optional[pathlib.Path]:
    link = base_results / "LATEST"
    pointer = base_results / "LATEST.path"
    if link.is_symlink():
        try:
            return link.resolve(strict=True)
        except FileNotFoundError:
            return None
    if link.exists() and link.is_dir():
        # If someone created a real dir named LATEST, accept it
        return link.resolve()
    if pointer.exists():
        target = pathlib.Path(pointer.read_text(encoding="utf-8").strip())
        return target if target.exists() else None
    return None

def main():
    results = pathlib.Path("results").resolve()
    run = resolve_latest(results)
    if not run:
        print("No latest artifacts found. Try: make demo && make report")
        print("Expected results/LATEST (symlink) or results/LATEST.path to point to a valid run.")
        return 1
    svg = run / "summary.svg"
    csv = run / "summary.csv"
    missing = [p for p in (svg, csv) if not p.exists()]
    if missing:
        print("Missing artifacts:", ", ".join(str(m) for m in missing))
        print("Try: make demo && make report")
        return 1
    cmd = opener_cmd()
    if cmd:
        try:
            subprocess.run(cmd + [str(svg)], check=False)
            subprocess.run(cmd + [str(csv)], check=False)
        except Exception:
            pass
    print(f"SVG: {svg}")
    print(f"CSV: {csv}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

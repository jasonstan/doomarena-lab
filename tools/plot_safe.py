#!/usr/bin/env python3
"""
Safe plotting wrapper:
  - If results/<outdir>/summary.csv has rows -> call scripts/plot_results.py
  - Else -> write a placeholder SVG so CI can still publish artifacts
"""
import csv
import subprocess
import sys
from pathlib import Path

def has_rows(csv_path: Path) -> bool:
    try:
        with csv_path.open(newline="") as f:
            rdr = csv.DictReader(f)
            for _ in rdr:
                return True
    except Exception:
        return False
    return False

def write_placeholder(svg_path: Path, message: str = "No data to plot") -> None:
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    # Minimal inline SVG (no matplotlib dependency here)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">
    <rect width="100%" height="100%" fill="#f6f6f6"/>
    <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle"
          font-family="sans-serif" font-size="20" fill="#666">{message}</text>
    </svg>'''
    svg_path.write_text(svg, encoding="utf-8")

def main() -> int:
    # Accept either --outdir PATH or a positional outdir
    args = sys.argv[1:]
    outdir = None
    for i, arg in enumerate(args):
        if arg == "--outdir" and i + 1 < len(args):
            outdir = args[i + 1]
    if outdir is None and args:
        outdir = args[0]
    if outdir is None:
        print("usage: plot_safe.py --outdir <RUN_DIR>", file=sys.stderr)
        return 2

    out = Path(outdir)
    csv_path = out / "summary.csv"
    svg_path = out / "summary.svg"

    if not csv_path.exists() or not has_rows(csv_path):
        write_placeholder(svg_path)
        print(f"Wrote placeholder plot to {svg_path}")
        return 0

    # Try to call the original plotter; on failure, fall back to placeholder
    try:
        result = subprocess.run(
            [sys.executable, "-m", "scripts.plot_results", "--outdir", str(out)],
            check=False,
        )
        if result.returncode != 0:
            write_placeholder(svg_path, "Plot failed; placeholder")
            print(
                "plot_results.py failed (rc="
                f"{result.returncode}); wrote placeholder {svg_path}"
            )
        return 0
    except Exception as exc:  # pragma: no cover - defensive
        write_placeholder(svg_path, "Plot error; placeholder")
        print(f"plot_safe: exception {exc}; wrote placeholder {svg_path}")
        return 0

if __name__ == "__main__":
    raise SystemExit(main())

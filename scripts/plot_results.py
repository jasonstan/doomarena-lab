#!/usr/bin/env python3
"""
Plot grouped bars of trial-weighted ASR per experiment from results/<RUN_DIR>/summary.csv.
Usage:
    python scripts/plot_results.py --outdir results/<RUN_DIR>
Produces:
    <outdir>/summary.svg
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
import matplotlib

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt

from scripts._lib import read_summary, weighted_asr_by_exp, ensure_dir


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    """Compatibility wrapper for tests expecting load_rows helper."""
    raw_rows = read_summary(csv_path)
    normalised: list[dict[str, str]] = []
    for row in raw_rows:
        exp = (row.get("exp") or row.get("experiment") or "").strip()
        if exp:
            if row.get("exp") == exp:
                normalised.append(row)
            else:
                updated = dict(row)
                updated["exp"] = exp
                normalised.append(updated)
        else:
            updated = dict(row)
            updated["exp"] = "<unknown>"
            normalised.append(updated)
    return normalised


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--outdir",
        default="results",
        help="path to results/<RUN_DIR> (default: results)",
    )
    ap.add_argument(
        "--exp",
        default="",
        help="optional experiment filter (unused placeholder for CLI parity)",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    outdir = Path(args.outdir)
    ensure_dir(outdir)
    rows = load_rows(outdir / "summary.csv")
    data = weighted_asr_by_exp(rows)

    # If no data, write a tiny placeholder chart (plot_safe also covers this in CI)
    if not data:
        fig = plt.figure(figsize=(6.4, 3.6))
        plt.text(0.5, 0.5, "No data to plot", ha="center", va="center")
        plt.axis("off")
        fig.tight_layout()
        fig.savefig(outdir / "summary.svg", format="svg")
        fig.savefig(outdir / "summary.png", format="png")
        plt.close(fig)
        return 0

    exps = sorted(data.keys())
    vals = [data[e] for e in exps]

    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar(exps, vals)
    ax.set_ylim(0, 1)
    ax.set_ylabel("ASR (successes ÷ trials)")
    ax.set_title("Attack Success Rate by Experiment")
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(outdir / "summary.svg", format="svg")
    fig.savefig(outdir / "summary.png", format="png")
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


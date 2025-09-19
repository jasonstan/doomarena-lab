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
from pathlib import Path
import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt

from scripts._lib import read_summary, weighted_asr_by_exp, ensure_dir


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True, help="path to results/<RUN_DIR>")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    outdir = Path(args.outdir)
    ensure_dir(outdir)
    rows = read_summary(outdir / "summary.csv")
    data = weighted_asr_by_exp(rows)

    # If no data, write a tiny placeholder chart (plot_safe also covers this in CI)
    if not data:
        fig = plt.figure(figsize=(6.4, 3.6))
        plt.text(0.5, 0.5, "No data to plot", ha="center", va="center")
        plt.axis("off")
        fig.tight_layout()
        fig.savefig(outdir / "summary.svg", format="svg")
        plt.close(fig)
        return 0

    exps = sorted(data.keys())
    vals = [data[e] for e in exps]

    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar(exps, vals)
    ax.set_ylim(0, 1)
    ax.set_ylabel("ASR (trial-weighted)")
    ax.set_title("Attack Success Rate by Experiment")
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(outdir / "summary.svg", format="svg")
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


#!/usr/bin/env python3
"""Generate aggregated ASR plots from ``results/summary.csv``."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import csv, pathlib, statistics
from collections import defaultdict
import argparse
import sys
from typing import Dict, List, Optional, Tuple

CSV = pathlib.Path("results/summary.csv")
OUT_SVG = pathlib.Path("results/summary.svg")
OUT_PNG = pathlib.Path("results/summary.png")


def load_rows(csv_path: pathlib.Path) -> List[Tuple[str, float]]:
    """Return ``(experiment, asr)`` rows from the CSV, normalising headers."""

    rows: List[Tuple[str, float]] = []
    with csv_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return rows
        for raw in reader:
            if not raw:
                continue
            normalised: Dict[str, object] = {}
            for key, value in raw.items():
                if key is None:
                    continue
                normalised[key.strip().lower()] = value

            if "exp" not in normalised:
                continue

            asr_source: Optional[object]
            if "asr" in normalised:
                asr_source = normalised["asr"]
            else:
                asr_source = normalised.get("attack_success_rate")
            if asr_source is None:
                continue

            try:
                asr_value = float(asr_source)
            except (TypeError, ValueError):
                continue

            exp_value = normalised.get("exp", "")
            exp_text = str(exp_value).strip() if exp_value is not None else ""
            if not exp_text:
                exp_text = "<unknown>"
            rows.append((exp_text, asr_value))
    return rows


def aggregate_means(rows: List[Tuple[str, float]]) -> Tuple[List[str], List[float]]:
    """Aggregate mean ASR per experiment name."""

    grouped: Dict[str, List[float]] = defaultdict(list)
    for exp, asr in rows:
        grouped[exp].append(asr)

    experiments = sorted(grouped.keys())
    means = [statistics.fmean(grouped[exp]) for exp in experiments]
    return experiments, means


def plot_summary(experiments: List[str], means: List[float]) -> None:
    """Render the summary plot and write SVG + PNG outputs."""

    if not experiments:
        raise SystemExit("No usable rows in results/summary.csv")

    fig_width = 6 + 0.5 * max(len(experiments) - 1, 0)
    fig, ax = plt.subplots(figsize=(fig_width, 4))
    positions = range(len(experiments))
    ax.bar(positions, means, width=0.6)

    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("ASR")
    if len(experiments) == 1:
        ax.set_title(f"Attack Success Rate — {experiments[0]}")
    else:
        ax.set_title("Attack Success Rate by Experiment")

    ax.set_xticks(list(positions))
    ax.set_xticklabels(
        experiments,
        rotation=20 if len(experiments) > 1 else 0,
        ha="right" if len(experiments) > 1 else "center",
    )
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.tight_layout()
    OUT_SVG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_SVG, bbox_inches="tight")
    fig.savefig(OUT_PNG, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {OUT_SVG} and {OUT_PNG}")


def parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot aggregated ASR results.")
    parser.add_argument(
        "--exp",
        help="Unused; maintained for backwards compatibility with older Makefile targets.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    parse_args(argv)

    if not CSV.exists():
        raise SystemExit("results/summary.csv not found; run `make report` first")

    rows = load_rows(CSV)
    if not rows:
        raise SystemExit("No usable rows in results/summary.csv")

    experiments, means = aggregate_means(rows)
    plot_summary(experiments, means)
    return 0


if __name__ == "__main__":
    sys.exit(main())

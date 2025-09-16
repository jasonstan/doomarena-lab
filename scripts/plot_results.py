#!/usr/bin/env python3
"""Generate aggregated ASR plots from ``results/summary.csv``."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import argparse
import csv
import math
import pathlib
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

@dataclass
class SummaryRow:
    exp: str
    asr: Optional[float]
    trials: Optional[float]
    successes: Optional[float]


def load_rows(csv_path: pathlib.Path) -> List[SummaryRow]:
    """Return rows from the CSV with normalised headers."""

    rows: List[SummaryRow] = []
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

            exp_value = normalised.get("exp", "")
            exp_text = str(exp_value).strip() if exp_value is not None else ""
            if not exp_text:
                exp_text = "<unknown>"
            asr_source: Optional[object]
            if "asr" in normalised:
                asr_source = normalised["asr"]
            else:
                asr_source = normalised.get("attack_success_rate")

            def parse_optional_float(value: Optional[object]) -> Optional[float]:
                if value is None:
                    return None
                if isinstance(value, str):
                    value = value.strip()
                    if not value:
                        return None
                try:
                    parsed = float(value)
                except (TypeError, ValueError):
                    return None
                if math.isnan(parsed):
                    return None
                return parsed

            asr_value = parse_optional_float(asr_source)
            trials_value = parse_optional_float(normalised.get("trials"))
            successes_value = parse_optional_float(normalised.get("successes"))

            rows.append(
                SummaryRow(
                    exp=exp_text,
                    asr=asr_value,
                    trials=trials_value,
                    successes=successes_value,
                )
            )
    return rows


def weighted_asr_by_exp(rows: Iterable[SummaryRow]) -> Dict[str, float]:
    """Compute trial-weighted ASR per experiment.

    Uses total successes / total trials when available, falling back to
    sum(asr * trials) / sum(trials) if successes is missing.
    """

    totals_succ: Dict[str, float] = defaultdict(float)
    totals_trials: Dict[str, float] = defaultdict(float)

    for row in rows:
        exp = row.exp or ""
        trials = row.trials
        if trials is None:
            continue

        if row.successes is None and row.asr is None:
            continue

        totals_trials[exp] += float(trials)

        if row.successes is not None:
            totals_succ[exp] += float(row.successes)
        elif row.asr is not None:
            totals_succ[exp] += float(row.asr) * float(trials)

    return {
        exp: (totals_succ[exp] / total_trials) if total_trials else float("nan")
        for exp, total_trials in totals_trials.items()
    }


def plot_summary(
    experiments: List[str],
    means: List[float],
    svg_path: pathlib.Path,
    png_path: pathlib.Path,
) -> None:
    """Render the summary plot and write SVG + PNG outputs."""

    if not experiments:
        raise SystemExit("No usable rows in summary data")

    fig_width = 6 + 0.5 * max(len(experiments) - 1, 0)
    fig, ax = plt.subplots(figsize=(fig_width, 4))
    positions = range(len(experiments))
    ax.bar(positions, means, width=0.6)

    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("ASR (successes ÷ trials)")
    if len(experiments) == 1:
        ax.set_title(f"Attack Success Rate — {experiments[0]}")
    else:
        ax.set_title("Attack Success Rate by Experiment")

    fig.text(
        0.02,
        0.02,
        "Bars are weighted by total trials per experiment.",
        ha="left",
        va="bottom",
        fontsize=8,
        color="0.3",
    )

    ax.set_xticks(list(positions))
    ax.set_xticklabels(
        experiments,
        rotation=20 if len(experiments) > 1 else 0,
        ha="right" if len(experiments) > 1 else "center",
    )
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.tight_layout()
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(svg_path, bbox_inches="tight")
    fig.savefig(png_path, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {svg_path} and {png_path}")


def parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot aggregated ASR results.")
    parser.add_argument(
        "--exp",
        help="Unused; maintained for backwards compatibility with older Makefile targets.",
    )
    parser.add_argument(
        "--outdir",
        default="results",
        help="Directory containing summary.csv and where plots should be written",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    base_dir = pathlib.Path(args.outdir).expanduser()
    csv_path = base_dir / "summary.csv"
    svg_path = base_dir / "summary.svg"
    png_path = base_dir / "summary.png"

    if not csv_path.exists():
        raise SystemExit(f"{csv_path} not found; run `make report` first")

    rows = load_rows(csv_path)
    aggregates = weighted_asr_by_exp(rows)
    if not aggregates:
        raise SystemExit("No usable rows in summary data")

    experiments = sorted(aggregates.keys())
    means = [aggregates[exp] for exp in experiments]
    plot_summary(experiments, means, svg_path, png_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

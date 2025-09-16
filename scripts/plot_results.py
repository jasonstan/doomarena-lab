#!/usr/bin/env python3
"""Generate quick plots from results/summary.csv."""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SUMMARY_CSV = Path("results/summary.csv")
PLOTS_DIR = Path("results/plots")
ASR_BY_SEED_PATH = PLOTS_DIR / "asr_by_seed.png"
ASR_OVER_TIME_PATH = PLOTS_DIR / "asr_over_time.png"
SUMMARY_SVG_PATH = Path("results/summary.svg")
SUMMARY_PNG_PATH = Path("results/summary.png")


@dataclass
class SummaryRow:
    """Typed representation of a single summary.csv row."""

    run_at: datetime
    exp: str
    seed: str
    asr: float


def parse_run_at(raw: str) -> Optional[datetime]:
    """Parse an ISO timestamp, normalising to naive UTC datetimes."""

    if not raw:
        return None

    text = raw.strip()
    if not text:
        return None

    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def extract_seed(raw: Any) -> str:
    """Extract a representative seed value from the CSV column."""

    if raw is None:
        return ""
    text = str(raw)
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if parts:
        return parts[0]
    return text.strip()


def load_rows(path: Path) -> List[SummaryRow]:
    """Load and validate rows from the summary CSV."""

    if not path.exists():
        print(f"No summary CSV found at {path}; nothing to plot.")
        return []

    with path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows: List[SummaryRow] = []
        for raw in reader:
            run_at = parse_run_at(raw.get("run_at", ""))
            if run_at is None:
                exp_id = raw.get("exp_id", "<unknown>")
                print(f"Skipping run {exp_id}: invalid timestamp '{raw.get('run_at')}'.")
                continue
            try:
                asr = float(raw.get("asr", ""))
            except (TypeError, ValueError):
                exp_id = raw.get("exp_id", "<unknown>")
                print(f"Skipping run {exp_id}: invalid ASR '{raw.get('asr')}'.")
                continue
            exp = raw.get("exp") or ""
            seed = extract_seed(raw.get("seeds", ""))
            rows.append(
                SummaryRow(
                    run_at=run_at,
                    exp=exp,
                    seed=seed,
                    asr=asr,
                )
            )

    if not rows:
        print(f"No rows found in {path}; nothing to plot.")
    return rows


def latest_by_seed(rows: Iterable[SummaryRow]) -> Dict[str, SummaryRow]:
    """Return the most recent row per seed."""

    latest: Dict[str, SummaryRow] = {}
    for row in rows:
        existing = latest.get(row.seed)
        if existing is None or row.run_at > existing.run_at:
            latest[row.seed] = row
    return latest


def sort_seed_items(items: Iterable[tuple[str, SummaryRow]]) -> List[tuple[str, SummaryRow]]:
    """Sort seed-summary pairs numerically when possible."""

    def sort_key(item: tuple[str, SummaryRow]):
        seed, _ = item
        try:
            return (0, int(seed))
        except (TypeError, ValueError):
            return (1, seed)

    return sorted(items, key=sort_key)


def plot_asr_by_seed(rows: Iterable[SummaryRow], exp: str) -> None:
    latest_rows = sort_seed_items(latest_by_seed(rows).items())
    if not latest_rows:
        print(f"No seed data found for experiment '{exp}'; skipping ASR-by-seed plot.")
        return

    seeds = [seed for seed, _ in latest_rows]
    asrs = [row.asr for _, row in latest_rows]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(seeds, asrs)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Attack Success Rate")
    ax.set_xlabel("Seed")
    ax.set_title(f"ASR by seed – {exp}")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(ASR_BY_SEED_PATH, dpi=150)
    plt.close(fig)
    print(f"Wrote {ASR_BY_SEED_PATH}")


def plot_asr_over_time(rows: Iterable[SummaryRow], exp: str) -> None:
    sorted_rows = sorted(rows, key=lambda row: row.run_at)
    if not sorted_rows:
        print(f"No time-series data found for experiment '{exp}'; skipping ASR-over-time plot.")
        return

    timestamps = [row.run_at for row in sorted_rows]
    asrs = [row.asr for row in sorted_rows]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(timestamps, asrs, marker="o")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Attack Success Rate")
    ax.set_xlabel("Run time")
    ax.set_title(f"ASR over time – {exp}")
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.autofmt_xdate()
    fig.tight_layout()
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(ASR_OVER_TIME_PATH, dpi=150)
    plt.close(fig)
    print(f"Wrote {ASR_OVER_TIME_PATH}")


def mean_asr_by_exp(rows: Iterable[SummaryRow]) -> Dict[str, float]:
    """Compute the mean ASR for each experiment."""

    totals: Dict[str, float] = defaultdict(float)
    counts: Dict[str, int] = defaultdict(int)
    for row in rows:
        exp = row.exp or ""
        totals[exp] += row.asr
        counts[exp] += 1

    means: Dict[str, float] = {}
    for exp, total in totals.items():
        if counts[exp]:
            means[exp] = total / counts[exp]
    return means


def plot_summary(rows: Iterable[SummaryRow]) -> None:
    """Render the summary.svg/png aggregated by experiment."""

    means = mean_asr_by_exp(rows)
    if not means:
        print("No experiments found; skipping summary plot.")
        return

    items = sorted(means.items(), key=lambda item: item[0])
    labels = [label for label, _ in items]
    values = [value for _, value in items]

    fig, ax = plt.subplots(figsize=(6, 4))
    x_positions = range(len(labels))
    ax.bar(x_positions, values)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Mean Attack Success Rate")
    ax.set_xlabel("Experiment")
    ax.set_title("Mean ASR by experiment")
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(labels, rotation=20 if len(labels) > 1 else 0)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()

    SUMMARY_SVG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(SUMMARY_SVG_PATH, bbox_inches="tight")
    fig.savefig(SUMMARY_PNG_PATH, dpi=144, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {SUMMARY_SVG_PATH}")
    print(f"Wrote {SUMMARY_PNG_PATH}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate quick ASR plots from summary CSV data.")
    parser.add_argument("--exp", help="Experiment name to filter results for detailed plots.")
    args = parser.parse_args(argv)

    rows = load_rows(SUMMARY_CSV)
    if not rows:
        return 0

    plot_summary(rows)

    if args.exp:
        exp_rows = [row for row in rows if row.exp == args.exp]
        if not exp_rows:
            print(
                f"No results found for experiment '{args.exp}' in {SUMMARY_CSV}; skipping detailed plots."
            )
            return 0

        plot_asr_by_seed(exp_rows, args.exp)
        plot_asr_over_time(exp_rows, args.exp)
    return 0


if __name__ == "__main__":
    sys.exit(main())

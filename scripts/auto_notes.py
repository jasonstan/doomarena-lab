"""Generate a Markdown summary for the latest experiment sweep.

This script reads ``results/summary.csv`` (case-insensitive headers) and writes a
human-readable report to ``results/summary.md``. The table aggregates trials and
successes per experiment and reports a trial-weighted (micro-average) attack
success rate (ASR). The Markdown also links to the generated
``results/summary.svg`` chart and records helpful invocation hints.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

SUMMARY_CSV = Path("results/summary.csv")
SUMMARY_MD = Path("results/summary.md")


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _normalise_row(row: Dict[str, str]) -> Dict[str, str]:
    normalised: Dict[str, str] = {}
    for key, value in row.items():
        if key is None:
            continue
        key_lower = key.strip().lower()
        if not key_lower:
            continue
        normalised[key_lower] = value
    return normalised


def _value_for_keys(row: Dict[str, str], *keys: str) -> Optional[str]:
    for key in keys:
        if key in row:
            return row[key]
    return None


def load_summary(csv_path: Path) -> List[Dict[str, str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing summary CSV at {csv_path}")
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [_normalise_row(row) for row in reader]


class ExperimentRow:
    __slots__ = (
        "name",
        "trials",
        "successes",
        "has_successes",
        "weighted_asr",
        "micro_asr",
    )

    def __init__(
        self,
        name: str,
        trials: int,
        successes: Optional[int],
        has_successes: bool,
        weighted_asr: float,
        micro_asr: float,
    ) -> None:
        self.name = name
        self.trials = trials
        self.successes = successes
        self.has_successes = has_successes
        self.weighted_asr = weighted_asr
        self.micro_asr = micro_asr


def aggregate(rows: Iterable[Dict[str, str]]) -> List[ExperimentRow]:
    aggregates: Dict[str, Dict[str, object]] = {}

    for row in rows:
        exp_name = _value_for_keys(row, "exp", "experiment")
        if exp_name is None:
            continue
        exp = exp_name.strip()
        if not exp:
            continue

        trials_value = _parse_int(_value_for_keys(row, "trials"))
        successes_value = _parse_int(_value_for_keys(row, "successes", "success"))
        asr_value = _parse_float(
            _value_for_keys(row, "asr", "attack_success_rate", "attack success rate")
        )

        entry = aggregates.setdefault(
            exp,
            {
                "trials": 0,
                "successes": 0,
                "has_successes": False,
                "weighted_asr": 0.0,
            },
        )

        if isinstance(trials_value, int):
            entry["trials"] = int(entry["trials"]) + trials_value
        if successes_value is not None:
            entry["successes"] = int(entry["successes"]) + successes_value
            entry["has_successes"] = True
        if asr_value is not None and trials_value is not None:
            entry["weighted_asr"] = float(entry["weighted_asr"]) + (asr_value * trials_value)

    aggregated_rows: List[ExperimentRow] = []
    for exp, entry in aggregates.items():
        trials = int(entry["trials"])
        weighted_asr = float(entry["weighted_asr"])
        has_successes = bool(entry["has_successes"])
        successes: Optional[int]
        if has_successes:
            successes = int(entry["successes"])
            micro_asr = successes / trials if trials > 0 else 0.0
        else:
            successes = None
            micro_asr = weighted_asr / trials if trials > 0 else 0.0
        aggregated_rows.append(
            ExperimentRow(
                name=exp,
                trials=trials,
                successes=successes,
                has_successes=has_successes,
                weighted_asr=weighted_asr,
                micro_asr=micro_asr,
            )
        )

    aggregated_rows.sort(key=lambda item: (-item.micro_asr, item.name))
    return aggregated_rows


def render_markdown(experiments: List[ExperimentRow]) -> str:
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    total_trials = sum(item.trials for item in experiments)
    total_success_equiv = 0.0
    total_successes_reported = 0
    has_success_counts = any(item.has_successes for item in experiments)

    for item in experiments:
        if item.has_successes and item.successes is not None:
            total_success_equiv += item.successes
            total_successes_reported += item.successes
        else:
            total_success_equiv += item.weighted_asr

    overall_micro = (total_success_equiv / total_trials) if total_trials > 0 else 0.0

    lines: List[str] = []
    lines.append(f"# Experiment summary — {timestamp}")
    lines.append("")
    lines.append(f"- Experiments: {len(experiments)}")
    lines.append(f"- Total trials: {total_trials}")
    if has_success_counts:
        lines.append(f"- Total successes: {total_successes_reported}")
    else:
        lines.append("- Total successes: n/a")
    lines.append(f"- Micro-average ASR: {overall_micro * 100:.1f}%")
    lines.append("")
    lines.append(
        "The bar chart below shows trial-weighted attack success rates per experiment "
        "(micro-averaged by trials)."
    )
    lines.append("")
    lines.append("![ASR summary](summary.svg)")
    lines.append("")
    lines.append("| Experiment | Trials | Successes | ASR (%) |")
    lines.append("| --- | --- | --- | --- |")

    for item in experiments:
        successes_display = str(item.successes) if item.successes is not None else "–"
        lines.append(
            f"| {item.name} | {item.trials} | {successes_display} | {item.micro_asr * 100:.1f}% |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "*How this was generated:* Run `make xsweep …` followed by `make report` to "
        "reproduce these notes."
    )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    rows = load_summary(SUMMARY_CSV)
    experiments = aggregate(rows)
    markdown = render_markdown(experiments)
    SUMMARY_MD.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()

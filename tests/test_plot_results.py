from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List
from xml.etree import ElementTree as ET

import pytest

# NOTE: The summary plot reports trial-weighted micro-average ASR values.


def _parse_optional_float(value: object | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        value = text
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_fixture_rows(csv_path: Path) -> List[Dict[str, float | str | None]]:
    """Load rows using a case-insensitive header map."""

    rows: List[Dict[str, float | str | None]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return rows
        for raw in reader:
            if not raw:
                continue
            normalised: Dict[str, object | None] = {}
            for key, value in raw.items():
                if key is None:
                    continue
                normalised[key.strip().lower()] = value

            exp = str(normalised.get("exp", "") or "").strip()
            if not exp:
                exp = "<unknown>"

            asr_source = normalised.get("asr")
            if asr_source is None:
                asr_source = normalised.get("attack_success_rate")

            rows.append(
                {
                    "exp": exp,
                    "trials": _parse_optional_float(normalised.get("trials")),
                    "successes": _parse_optional_float(normalised.get("successes")),
                    "asr": _parse_optional_float(asr_source),
                }
            )
    return rows


def _trial_weighted_means(rows: Iterable[Dict[str, float | str | None]]) -> Dict[str, float]:
    """Compute trial-weighted micro-averages.

    The trials column acts as the weight, ensuring the resulting ASR is the
    micro-average of successes divided by trials. When successes are missing we
    fall back to the weighted ASR values (``asr * trials``).
    """

    totals_trials: Dict[str, float] = defaultdict(float)
    totals_successes: Dict[str, float] = defaultdict(float)
    fallback_totals: Dict[str, float] = defaultdict(float)
    has_explicit_successes: Dict[str, bool] = defaultdict(bool)

    for row in rows:
        exp = str(row.get("exp") or "")
        trials = row.get("trials")
        if trials is None:
            continue

        trials_value = float(trials)
        if trials_value <= 0:
            continue

        totals_trials[exp] += trials_value

        successes_value = row.get("successes")
        if successes_value is not None:
            totals_successes[exp] += float(successes_value)
            has_explicit_successes[exp] = True
            continue

        asr_value = row.get("asr")
        if asr_value is not None:
            fallback_totals[exp] += float(asr_value) * trials_value

    aggregates: Dict[str, float] = {}
    for exp, total_trials in totals_trials.items():
        if total_trials <= 0:
            continue
        numerator = (
            totals_successes[exp]
            if has_explicit_successes[exp]
            else fallback_totals[exp]
        )
        aggregates[exp] = numerator / total_trials
    return aggregates


def _load_plot_module():
    spec = importlib.util.spec_from_file_location(
        "plot_results_module", Path("scripts/plot_results.py")
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("Unable to import plot_results module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _count_bars(svg_path: Path) -> int:
    tree = ET.parse(svg_path)
    root = tree.getroot()
    namespace = "{http://www.w3.org/2000/svg}"

    bar_count = 0
    for patch in root.findall(f".//{namespace}g"):
        patch_id = patch.attrib.get("id", "")
        if not patch_id.startswith("patch_"):
            continue
        for child in patch:
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "path" and "clip-path" in child.attrib:
                bar_count += 1
                break
    return bar_count


def test_plot_results_smoke():
    pytest.importorskip("matplotlib")

    summary_path = Path("results/summary.csv")
    if not summary_path.exists():
        pytest.skip("summary.csv missing; skipping plot smoke test")

    fixture_rows = _load_fixture_rows(summary_path)
    aggregates_from_fixture = _trial_weighted_means(fixture_rows)
    if not aggregates_from_fixture:
        pytest.skip("No usable rows in summary.csv; skipping plot smoke test")

    expected_files = [
        Path("results/summary.svg"),
        Path("results/summary.png"),
    ]

    for plot_file in expected_files:
        if plot_file.exists():
            plot_file.unlink()

    subprocess.run(
        [sys.executable, "scripts/plot_results.py", "--exp", "airline_escalating_v1"],
        check=True,
    )

    plot_module = _load_plot_module()
    module_rows = plot_module.load_rows(summary_path)
    module_aggregates = plot_module.weighted_asr_by_exp(module_rows)

    assert module_aggregates, "plot_results produced no aggregates"
    assert module_aggregates.keys() == aggregates_from_fixture.keys()
    for exp, expected_value in aggregates_from_fixture.items():
        assert module_aggregates[exp] == pytest.approx(expected_value)

    svg_path = Path("results/summary.svg")
    svg_text = svg_path.read_text(encoding="utf-8")
    assert "ASR (successes ÷ trials)" in svg_text
    assert _count_bars(svg_path) == len(aggregates_from_fixture)

    for plot_file in expected_files:
        assert plot_file.exists(), f"{plot_file} was not created"
        assert plot_file.stat().st_size > 0, f"{plot_file} is empty"


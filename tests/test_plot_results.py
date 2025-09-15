from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def test_plot_results_smoke():
    pytest.importorskip("matplotlib")

    summary_path = Path("results/summary.csv")
    if not summary_path.exists():
        pytest.skip("summary.csv missing; skipping plot smoke test")

    plots_dir = Path("results/plots")
    expected_files = [
        plots_dir / "asr_by_seed.png",
        plots_dir / "asr_over_time.png",
    ]

    for plot_file in expected_files:
        if plot_file.exists():
            plot_file.unlink()

    subprocess.run(
        [sys.executable, "scripts/plot_results.py", "--exp", "airline_escalating_v1"],
        check=True,
    )

    for plot_file in expected_files:
        assert plot_file.exists(), f"{plot_file} was not created"
        assert plot_file.stat().st_size > 0, f"{plot_file} is empty"


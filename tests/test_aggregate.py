import subprocess
import sys
from pathlib import Path

import pandas as pd


EXPECTED_COLUMNS = [
    "timestamp",
    "git_sha",
    "exp",
    "seed",
    "mode",
    "trials",
    "successes",
    "asr",
    "py_version",
    "path",
]


def test_aggregate_generates_summary():
    subprocess.check_call(
        [
            sys.executable,
            "scripts/run_batch.py",
            "--exp",
            "airline_escalating_v1",
            "--seeds",
            "99",
            "--trials",
            "2",
        ]
    )
    subprocess.check_call(["make", "report"])

    csv_path = Path("results/summary.csv")
    assert csv_path.exists()
    df = pd.read_csv(csv_path)
    assert len(df) >= 1
    for column in EXPECTED_COLUMNS:
        assert column in df.columns

    asr_values = pd.to_numeric(df["asr"], errors="coerce")
    trials = pd.to_numeric(df["trials"], errors="coerce")
    successes = pd.to_numeric(df["successes"], errors="coerce")

    assert asr_values.between(0.0, 1.0).all()
    assert (trials >= successes).all()
    assert (trials >= 0).all()
    assert (successes >= 0).all()

    readme = Path("README.md").read_text(encoding="utf-8")
    assert "<!-- RESULTS:BEGIN -->" in readme
    assert "<!-- RESULTS:END -->" in readme

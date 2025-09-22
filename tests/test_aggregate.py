import subprocess
import sys
from pathlib import Path

import pandas as pd


EXPECTED_COLUMNS = [
    "exp_id",
    "exp",
    "config",
    "cfg_hash",
    "mode",
    "seeds",
    "trials",
    "successes",
    "asr",
    "sum_tokens",
    "avg_latency_ms",
    "sum_cost_usd",
    "git_commit",
    "run_at",
    "total_trials",
    "pre_denied",
    "called_trials",
    "pass_rate",
    "p50_ms",
    "p95_ms",
    "total_tokens",
    "post_warn",
    "post_deny",
    "top_reason",
    "calls_made",
    "tokens_prompt_sum",
    "tokens_completion_sum",
    "tokens_total_sum",
    "stopped_early",
    "budget_hit",
    "schema",
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
    assert list(df.columns) == EXPECTED_COLUMNS

    asr_values = pd.to_numeric(df["asr"], errors="coerce")
    trials = pd.to_numeric(df["trials"], errors="coerce")
    successes = pd.to_numeric(df["successes"], errors="coerce")

    assert asr_values.between(0.0, 1.0).all()
    assert (trials >= successes).all()
    assert (trials >= 0).all()
    assert (successes >= 0).all()

    assert df["exp_id"].astype(str).str.len().gt(0).all()
    assert df["exp"].astype(str).str.len().gt(0).all()
    assert df["config"].astype(str).str.len().gt(0).all()
    assert df["cfg_hash"].astype(str).str.len().gt(0).all()
    assert df["mode"].astype(str).str.len().gt(0).all()
    assert df["run_at"].astype(str).str.len().gt(0).all()

    readme = Path("README.md").read_text(encoding="utf-8")
    assert "<!-- RESULTS:BEGIN -->" in readme
    assert "<!-- RESULTS:END -->" in readme

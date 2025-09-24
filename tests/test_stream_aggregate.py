import csv
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest


COST_PER_ROW = 0.01
TOKENS_PER_ROW = 12
LATENCY_MS = 100.0


pytest.importorskip("yaml")


def _write_large_rows(rows_path: Path, *, count: int, exp_name: str) -> None:
    timestamp = "2024-01-01T00:00:00Z"
    with rows_path.open("w", encoding="utf-8") as handle:
        for index in range(count):
            payload = {
                "exp": exp_name,
                "seed": f"seed-{index % 5}",
                "success": index % 2 == 0,
                "callable": True,
                "latency_ms": LATENCY_MS,
                "prompt_tokens": 5,
                "completion_tokens": 7,
                "total_tokens": TOKENS_PER_ROW,
                "cost_usd": COST_PER_ROW,
                "pre_call_gate": {"decision": "allow"},
                "post_call_gate": {"decision": "allow"},
                "fail_reason": "",
                "timestamp": timestamp,
            }
            handle.write(json.dumps(payload))
            handle.write("\n")


def test_streaming_aggregator_handles_large_real_rows(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    base_dir = tmp_path / "runs"
    run_dir = base_dir / "exp-large"
    run_dir.mkdir(parents=True)

    run_meta = {
        "run_id": "run-001",
        "exp": "exp-large",
        "config": "{\"model\": \"demo\"}",
        "cfg_hash": "abcdef123456",
        "mode": "REAL",
        "seed": "seed-0",
        "started": "2024-01-01T00:00:00Z",
        "git_commit": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    }
    (run_dir / "run.json").write_text(json.dumps(run_meta), encoding="utf-8")

    row_count = 50000
    _write_large_rows(run_dir / "rows.jsonl", count=row_count, exp_name=run_meta["exp"])

    command = [
        sys.executable,
        "scripts/aggregate_results.py",
        "--outdir",
        str(base_dir),
    ]

    subprocess.run(command, check=True, cwd=repo_root)

    summary_path = base_dir / "summary.csv"
    report_path = base_dir / "run_report.json"

    assert summary_path.exists()
    assert report_path.exists()

    summary_first = summary_path.read_text(encoding="utf-8")
    report_first = json.loads(report_path.read_text(encoding="utf-8"))
    report_first.pop("generated_at", None)

    subprocess.run(command, check=True, cwd=repo_root)

    summary_second = summary_path.read_text(encoding="utf-8")
    report_second = json.loads(report_path.read_text(encoding="utf-8"))
    report_second.pop("generated_at", None)

    assert summary_first == summary_second
    assert report_first == report_second

    reader = csv.DictReader(io.StringIO(summary_first))
    rows = list(reader)
    assert len(rows) == 1
    summary_row = rows[0]

    expected_successes = (row_count + 1) // 2
    expected_tokens = row_count * TOKENS_PER_ROW
    expected_cost = row_count * COST_PER_ROW

    assert summary_row["trials"] == str(row_count)
    assert summary_row["successes"] == str(expected_successes)
    assert summary_row["sum_tokens"] == str(expected_tokens)
    assert summary_row["avg_latency_ms"] == f"{LATENCY_MS:.1f}"
    assert summary_row["sum_cost_usd"] == f"{expected_cost:.4f}"

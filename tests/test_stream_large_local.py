"""Local-only smoke test for streaming aggregation on large rows files."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tools.gen_rows import REASON_CODES, write_rows
from tools.aggregate import aggregate_stream
from scripts.aggregate_results import _RealRowsStats


@pytest.mark.skipif(os.environ.get("ENV") != "LOCAL_SMOKE", reason="local smoke only")
def test_stream_large_local(tmp_path: Path) -> None:
    count = 50_000
    run_dir = tmp_path / "smoke"
    rows_path = run_dir / "rows.jsonl"
    run_dir.mkdir(parents=True)

    write_rows(rows_path, count=count)

    run_meta = {
        "run_id": "smoke-run",
        "exp": "smoke_exp_stream",
        "cfg_hash": "deadbeefdeadbeefdeadbeefdeadbeef",
        "mode": "REAL",
        "seed": "seed-0",
        "started": "2024-01-01T00:00:00Z",
        "git_commit": "0123456789abcdef0123456789abcdef01234567",
    }
    (run_dir / "run.json").write_text(json.dumps(run_meta), encoding="utf-8")

    aggregate = aggregate_stream(
        rows_path,
        stats_factory=lambda run_dir, run_meta: _RealRowsStats(
            run_dir=run_dir, run_meta=run_meta
        ),
    )

    successes = 0
    reason_codes: set[str] = set()
    for row in aggregate.rows():
        assert row["exp"] == "smoke_exp_stream"
        assert isinstance(row["success"], bool)
        if row["success"]:
            successes += 1
        pre_gate = row.get("pre_call_gate", {})
        if isinstance(pre_gate, dict) and "reason_code" in pre_gate:
            reason_codes.add(pre_gate["reason_code"])

    summary = aggregate.summary

    assert summary["trials"] == count
    assert summary["successes"] == successes
    assert summary["sum_tokens"] > 0
    # All configured reason codes should appear at least once.
    assert reason_codes == set(REASON_CODES)

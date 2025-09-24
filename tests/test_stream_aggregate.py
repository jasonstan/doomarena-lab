import json
import subprocess
import sys
from pathlib import Path

import pytest


pytest.importorskip("yaml")


def _prepare_run(run_dir: Path, *, run_meta: dict, rows: list[str]) -> None:
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps(run_meta), encoding="utf-8")
    (run_dir / "rows.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_streaming_mode_matches_default(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    base_dir = tmp_path / "runs"
    default_dir = base_dir / "exp-default"
    stream_dir = base_dir / "exp-stream"

    run_meta = {
        "run_id": "run-001",
        "exp": "exp-small",
        "config": "{\"model\": \"demo\"}",
        "cfg_hash": "abcdef123456",
        "mode": "REAL",
        "seed": "seed-0",
        "started": "2024-01-01T00:00:00Z",
        "git_commit": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    }

    rows: list[str] = []
    malformed_lines = 0
    timestamp = "2024-01-01T00:00:00Z"
    for index in range(20):
        payload = {
            "exp": run_meta["exp"],
            "seed": f"seed-{index % 5}",
            "success": index % 2 == 0,
            "callable": True,
            "latency_ms": 100.0,
            "prompt_tokens": 5,
            "completion_tokens": 7,
            "total_tokens": 12,
            "cost_usd": 0.01,
            "pre_call_gate": {"decision": "allow"},
            "post_call_gate": {"decision": "allow"},
            "fail_reason": "",
            "timestamp": timestamp,
        }
        rows.append(json.dumps(payload))
    rows.append("{ this is not valid json")
    malformed_lines = 1

    _prepare_run(default_dir, run_meta=run_meta, rows=rows)
    _prepare_run(stream_dir, run_meta=run_meta, rows=rows)

    base_command = [
        sys.executable,
        "scripts/aggregate_results.py",
        "--outdir",
    ]

    subprocess.run(base_command + [str(default_dir)], check=True, cwd=repo_root)
    subprocess.run(
        base_command + [str(stream_dir), "--stream"],
        check=True,
        cwd=repo_root,
    )

    default_summary = (default_dir / "summary.csv").read_text(encoding="utf-8")
    stream_summary = (stream_dir / "summary.csv").read_text(encoding="utf-8")

    assert default_summary == stream_summary

    stream_run_json = json.loads((stream_dir / "run.json").read_text(encoding="utf-8"))
    assert stream_run_json.get("malformed_rows") == malformed_lines

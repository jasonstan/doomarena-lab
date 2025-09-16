import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from exp import load_config


def test_results_paths(tmp_path):
    base_config_path = Path("configs/airline_escalating_v1/exp.yaml")
    cfg = load_config(base_config_path)
    cfg["trials"] = 1

    seed = 777
    cfg["seeds"] = [seed]

    temp_config = tmp_path / "exp.yaml"
    with temp_config.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(cfg, handle)

    proc = subprocess.run(
        [sys.executable, "scripts/run_experiment.py", "--config", str(temp_config), "--seed", str(seed)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "ASR=" in proc.stdout
    assert "JSONL=" in proc.stdout

    normalized_cfg = load_config(temp_config)

    results_dir = Path("results") / str(normalized_cfg["exp"])
    jsonl_path = results_dir / f"{normalized_cfg['exp']}_seed{seed}.jsonl"
    summary_path = Path("results") / "summary.csv"

    assert jsonl_path.exists()
    assert summary_path.exists()

    header_event = None
    summary_event = None
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if header_event is None and payload.get("event") == "header":
                header_event = payload
            if payload.get("event") == "summary":
                summary_event = payload
    assert header_event is not None, "header event missing from JSONL"
    assert summary_event is not None, "summary event missing from JSONL"

    subprocess.check_call([sys.executable, "scripts/aggregate_results.py"])

    with summary_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    matching_rows = [
        row
        for row in rows
        if row.get("config") == temp_config.as_posix()
    ]
    assert matching_rows, "Summary row for seed not found"

    summary_row = matching_rows[-1]
    assert summary_row.get("exp") == normalized_cfg["exp"]
    assert summary_row.get("exp_id")
    assert str(seed) in (summary_row.get("seeds") or "")
    assert summary_row.get("mode") == header_event.get("mode")

    trials_csv = int(summary_row.get("trials", 0))
    successes_csv = int(summary_row.get("successes", 0))
    asr_csv = float(summary_row.get("asr", 0.0))

    trials_summary = int(summary_event.get("trials", 0))
    successes_summary = int(summary_event.get("successes", 0))
    asr_summary = float(summary_event.get("asr", 0.0))

    assert trials_csv == trials_summary
    assert successes_csv == successes_summary
    assert asr_csv == pytest.approx(asr_summary)

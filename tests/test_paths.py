import csv
import subprocess
import sys
from pathlib import Path

import yaml

from exp import load_config, make_exp_id


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
    exp_id = make_exp_id(normalized_cfg)

    results_dir = Path("results") / f"{normalized_cfg['exp']}_{exp_id}"
    jsonl_path = results_dir / f"seed{seed}.jsonl"
    summary_path = Path("results") / "summary.csv"

    assert jsonl_path.exists()
    assert summary_path.exists()

    with summary_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    matching_rows = [
        row
        for row in rows
        if row.get("exp") == normalized_cfg["exp"]
        and row.get("seed") == str(seed)
        and row.get("path") == jsonl_path.as_posix()
    ]
    assert matching_rows, "Summary row for seed not found"

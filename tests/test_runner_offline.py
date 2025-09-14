import os, json, subprocess, sys
import yaml

def test_runner_writes_jsonl_and_summary(tmp_path):
    # Load the baseline config and override output to a temp folder
    base_cfg_path = "configs/airline_escalating_v1/run.yaml"
    with open(base_cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["output"] = {"dir": str(tmp_path / "results"), "file": "run.jsonl"}
    cfg_path = tmp_path / "run.yaml"
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f)

    # Run the script
    proc = subprocess.run(
        [sys.executable, "scripts/taubench_airline_da.py", "--config", str(cfg_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    # Check stdout hints
    assert "ASR=" in proc.stdout
    assert "JSONL=" in proc.stdout

    # Check JSONL content
    out_file = os.path.join(cfg["output"]["dir"], cfg["output"]["file"])
    assert os.path.exists(out_file)
    with open(out_file, "r", encoding="utf-8") as f:
        lines = [json.loads(x) for x in f.read().splitlines()]
    assert lines[0]["event"] == "header"
    assert lines[-1]["event"] == "summary"
    assert lines[-1]["trials"] == cfg["trials"]

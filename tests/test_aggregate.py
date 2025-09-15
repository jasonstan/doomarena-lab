import subprocess
from pathlib import Path
import pandas as pd


def test_aggregate_generates_summary():
    subprocess.check_call(["make", "report"])
    csv_path = Path("results/summary.csv")
    assert csv_path.exists()
    df = pd.read_csv(csv_path)
    assert len(df) >= 1
    for col in ["run_id", "jsonl", "trials", "successes", "asr", "path", "mtime"]:
        assert col in df.columns
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "<!-- RESULTS:BEGIN -->" in readme
    assert "<!-- RESULTS:END -->" in readme

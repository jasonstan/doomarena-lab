import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd


def generate_if_needed(base_dir: Path) -> None:
    jsonl_files = list(base_dir.rglob("*.jsonl"))
    if jsonl_files:
        return
    cmd = [
        sys.executable,
        "scripts/taubench_airline_da_real.py",
        "--config",
        "configs/airline_escalating_v1/run.yaml",
    ]
    subprocess.run(cmd, check=True)


def parse_jsonl(path: Path):
    trials = successes = 0
    asr = None
    path_hint = "SHIM"
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            event = data.get("event")
            if event == "trial":
                trials += 1
                if data.get("success"):
                    successes += 1
            elif event == "summary":
                if {"trials", "successes", "asr"}.issubset(data):
                    trials = data["trials"]
                    successes = data["successes"]
                    asr = data["asr"]
                path_hint = data.get("path", path_hint)
    if asr is None and trials:
        asr = successes / trials
    return trials, successes, asr, path_hint


def main():
    base_dir = Path("results")
    base_dir.mkdir(exist_ok=True)
    generate_if_needed(base_dir)
    rows = []
    for path in base_dir.rglob("*.jsonl"):
        trials, successes, asr, path_hint = parse_jsonl(path)
        mtime_ts = path.stat().st_mtime
        mtime = datetime.fromtimestamp(mtime_ts, tz=timezone.utc).isoformat()
        rows.append(
            {
                "run_id": path.stem,
                "jsonl": path.as_posix(),
                "trials": trials,
                "successes": successes,
                "asr": asr,
                "path": path_hint,
                "mtime": mtime,
                "_mtime_ts": mtime_ts,
            }
        )
    if not rows:
        return
    df = pd.DataFrame(rows)
    df.sort_values("_mtime_ts", ascending=False, inplace=True)
    df.drop(columns=["_mtime_ts"], inplace=True)
    csv_path = base_dir / "summary.csv"
    df.to_csv(csv_path, index=False)
    md_path = base_dir / "summary.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("| run_id | ASR | trials | path |\n")
        f.write("| --- | --- | --- | --- |\n")
        for _, row in df.iterrows():
            link = f"[{row['run_id']}]({row['jsonl']})"
            asr = "" if row["asr"] is None else f"{row['asr']:.3f}"
            f.write(f"| {link} | {asr} | {row['trials']} | {row['path']} |\n")


if __name__ == "__main__":
    main()

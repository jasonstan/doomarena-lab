import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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


SEED_PATTERN = re.compile(r"_seed(?P<seed>\d+)\.jsonl$")


def parse_jsonl(path: Path):
    trials = successes = 0
    asr: Optional[float] = None
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


def get_current_commit() -> str:
    return (
        subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True)
        .strip()
    )


def extract_seed(path: Path) -> str:
    match = SEED_PATTERN.search(path.name)
    if match:
        return match.group("seed")
    return ""


def main():
    base_dir = Path("results")
    base_dir.mkdir(exist_ok=True)
    generate_if_needed(base_dir)
    rows = []
    commit = get_current_commit()
    for path in base_dir.rglob("*.jsonl"):
        trials, successes, asr, path_hint = parse_jsonl(path)
        mtime_ts = path.stat().st_mtime
        mtime = datetime.fromtimestamp(mtime_ts, tz=timezone.utc).isoformat()
        success_frac = f"{successes}/{trials}"
        asr_pct: Optional[float]
        if asr is not None:
            asr_pct = round(asr * 100, 1)
        else:
            asr_pct = None
        rows.append(
            {
                "run_id": path.stem,
                "jsonl": path.as_posix(),
                "trials": trials,
                "successes": successes,
                "success_frac": success_frac,
                "asr": asr,
                "asr_pct": asr_pct,
                "path": path_hint,
                "seed": extract_seed(path),
                "commit": commit,
                "mtime": mtime,
                "_mtime_ts": mtime_ts,
            }
        )
    if not rows:
        return
    df = pd.DataFrame(rows)
    df.sort_values("_mtime_ts", ascending=False, inplace=True)
    df.drop(columns=["_mtime_ts"], inplace=True)
    df["asr"] = df["asr"].apply(lambda value: round(value, 3) if value is not None else None)
    df["asr_pct"] = df["asr_pct"].apply(
        lambda value: round(value, 1) if value is not None else None
    )
    ordered_columns = [
        "run_id",
        "jsonl",
        "trials",
        "successes",
        "success_frac",
        "asr",
        "asr_pct",
        "path",
        "seed",
        "commit",
        "mtime",
    ]
    df = df[ordered_columns]
    df_for_csv = df.copy()
    df_for_csv["asr"] = df_for_csv["asr"].apply(
        lambda value: f"{value:.3f}" if pd.notna(value) else ""
    )
    df_for_csv["asr_pct"] = df_for_csv["asr_pct"].apply(
        lambda value: f"{value:.1f}" if pd.notna(value) else ""
    )
    csv_path = base_dir / "summary.csv"
    df_for_csv.to_csv(csv_path, index=False)
    md_path = base_dir / "summary.md"
    df_for_md = df.head(5)
    with md_path.open("w", encoding="utf-8") as f:
        f.write("| run_id | ASR | trials | path | seed |\n")
        f.write("| --- | --- | --- | --- | --- |\n")
        for _, row in df_for_md.iterrows():
            link = f"[{row['run_id']}]({row['jsonl']})"
            if pd.isna(row["asr"]):
                asr_display = ""
            else:
                asr_display = f"{row['asr']:.2f} ({row['success_frac']})"
            f.write(
                f"| {link} | {asr_display} | {row['trials']} | {row['path']} | {row['seed']} |\n"
            )


if __name__ == "__main__":
    main()

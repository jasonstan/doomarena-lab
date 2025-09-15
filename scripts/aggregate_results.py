import csv
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SUMMARY_COLUMNS = [
    "timestamp",
    "git_sha",
    "exp",
    "seed",
    "mode",
    "trials",
    "successes",
    "asr",
    "py_version",
    "path",
]

SEED_PATTERN = re.compile(r"_seed(?P<seed>\d+)\.jsonl$")


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


def parse_jsonl(path: Path) -> Tuple[int, int, float, Optional[str]]:
    summary: Optional[Dict] = None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("event") == "summary":
                summary = data
    if summary is None:
        raise RuntimeError(f"Missing summary in {path}")
    trials = int(summary.get("trials", 0))
    successes = int(summary.get("successes", 0))
    if successes > trials:
        successes = trials
    asr = summary.get("asr")
    if asr is None:
        asr = successes / trials if trials else 0.0
    mode = summary.get("mode")
    return trials, successes, float(asr), mode


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


def normalize_mode(mode: Optional[str]) -> str:
    if not mode:
        return "SHIM"
    value = str(mode).upper()
    if value not in {"REAL", "SHIM"}:
        return "SHIM"
    return value


def read_existing(summary_path: Path) -> Dict[Tuple[str, str], Dict[str, str]]:
    rows: Dict[Tuple[str, str], Dict[str, str]] = {}
    if not summary_path.exists():
        return rows
    with summary_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return rows
        if not set(SUMMARY_COLUMNS).issubset(set(reader.fieldnames)):
            return rows
        for row in reader:
            exp = row.get("exp", "")
            seed = row.get("seed", "")
            if exp:
                rows[(exp, seed)] = dict(row)
    return rows


def build_rows(base_dir: Path, existing: Dict[Tuple[str, str], Dict[str, str]]) -> List[Dict[str, str]]:
    commit = get_current_commit()
    py_version = platform.python_version()
    now_iso = datetime.now(timezone.utc).isoformat()
    rows: Dict[Tuple[str, str], Dict[str, str]] = dict(existing)
    seen_keys: set[Tuple[str, str]] = set()

    for path in sorted(base_dir.rglob("*.jsonl")):
        exp = path.parent.name
        seed = extract_seed(path)
        key = (exp, seed)
        trials, successes, asr, mode_hint = parse_jsonl(path)
        row = dict(rows.get(key, {}))
        timestamp = row.get("timestamp") or now_iso
        mode = normalize_mode(mode_hint or row.get("mode"))
        row.update(
            {
                "timestamp": timestamp,
                "git_sha": commit,
                "exp": exp,
                "seed": seed,
                "mode": mode,
                "trials": str(trials),
                "successes": str(successes),
                "asr": f"{asr:.6f}",
                "py_version": row.get("py_version") or py_version,
                "path": path.as_posix(),
            }
        )
        rows[key] = row
        seen_keys.add(key)

    normalized_rows: List[Dict[str, str]] = []
    for (exp, seed), row in rows.items():
        if seen_keys and (exp, seed) not in seen_keys:
            continue
        if not exp:
            continue
        normalized_rows.append({column: row.get(column, "") for column in SUMMARY_COLUMNS})

    normalized_rows.sort(
        key=lambda item: (
            item.get("exp", ""),
            int(item.get("seed", "0")) if item.get("seed", "").isdigit() else item.get("seed", ""),
        )
    )
    return normalized_rows


def write_summary(summary_path: Path, rows: List[Dict[str, str]]) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_summary_md(base_dir: Path, rows: List[Dict[str, str]]) -> None:
    md_path = base_dir / "summary.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    recent = sorted(rows, key=lambda item: item.get("timestamp", ""), reverse=True)[:5]
    with md_path.open("w", encoding="utf-8") as handle:
        handle.write("| exp | seed | mode | ASR | trials | successes | path |\n")
        handle.write("| --- | --- | --- | --- | --- | --- | --- |\n")
        for row in recent:
            asr_display = ""
            try:
                asr_value = float(row.get("asr", ""))
            except (TypeError, ValueError):
                asr_value = None
            if asr_value is not None:
                asr_display = f"{asr_value:.2f} ({row.get('successes', '')}/{row.get('trials', '')})"
            link = ""
            if row.get("path"):
                link = f"[{Path(row['path']).stem}]({row['path']})"
            handle.write(
                "| {exp} | {seed} | {mode} | {asr} | {trials} | {successes} | {link} |\n".format(
                    exp=row.get("exp", ""),
                    seed=row.get("seed", ""),
                    mode=row.get("mode", ""),
                    asr=asr_display,
                    trials=row.get("trials", ""),
                    successes=row.get("successes", ""),
                    link=link,
                )
            )


def main() -> None:
    base_dir = Path("results")
    base_dir.mkdir(exist_ok=True)
    generate_if_needed(base_dir)

    summary_path = base_dir / "summary.csv"
    existing_rows = read_existing(summary_path)
    rows = build_rows(base_dir, existing_rows)
    write_summary(summary_path, rows)
    write_summary_md(base_dir, rows)


if __name__ == "__main__":
    main()

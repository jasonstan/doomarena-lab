import csv
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from exp import SUMMARY_COLUMNS, read_summary as load_summary_rows

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
    if trials < 0:
        trials = 0
    successes = int(summary.get("successes", 0))
    if successes < 0:
        successes = 0
    if successes > trials:
        successes = trials
    asr = summary.get("asr")
    if asr is None:
        asr = successes / trials if trials else 0.0
    asr_value = float(asr)
    if asr_value < 0.0:
        asr_value = 0.0
    elif asr_value > 1.0:
        asr_value = 1.0
    mode = summary.get("mode")
    return trials, successes, asr_value, mode


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


def generate_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _git_diff_is_clean(args: Optional[List[str]] = None) -> bool:
    cmd = ["git", "diff", "--quiet"]
    if args:
        cmd.extend(args)
    result = subprocess.run(cmd, check=False)
    return result.returncode == 0


def repo_is_dirty() -> bool:
    if not _git_diff_is_clean():
        return True
    if not _git_diff_is_clean(["--cached"]):
        return True
    return False


def normalize_mode(mode: Optional[str]) -> str:
    if not mode:
        return "SHIM"
    value = str(mode).upper()
    if value not in {"REAL", "SHIM"}:
        return "SHIM"
    return value


def load_meta(jsonl_path: Path) -> Optional[Dict[str, Any]]:
    meta_path = jsonl_path.parent / "meta.json"
    if not meta_path.exists():
        return None
    try:
        with meta_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def read_existing(summary_path: Path) -> Dict[Tuple[str, str], Dict[str, str]]:
    rows: Dict[Tuple[str, str], Dict[str, str]] = {}
    for row in load_summary_rows(summary_path):
        exp = row.get("exp", "")
        seed = row.get("seed", "")
        if exp:
            rows[(exp, seed)] = dict(row)
    return rows


def build_rows(base_dir: Path, existing: Dict[Tuple[str, str], Dict[str, str]]) -> List[Dict[str, str]]:
    commit = get_current_commit()
    default_python_version = platform.python_version()
    now_iso = datetime.now(timezone.utc).isoformat()
    run_id = generate_run_id()
    repo_dirty = repo_is_dirty()
    rows: Dict[Tuple[str, str], Dict[str, str]] = dict(existing)
    seen_keys: set[Tuple[str, str]] = set()

    for path in sorted(base_dir.rglob("*.jsonl")):
        exp = path.parent.name
        seed = extract_seed(path)
        key = (exp, seed)
        trials, successes, asr, mode_hint = parse_jsonl(path)
        asr = max(0.0, min(1.0, asr))
        row = dict(rows.get(key, {}))
        meta = load_meta(path)

        timestamp = row.get("timestamp") or now_iso
        if meta and meta.get("timestamp"):
            timestamp = str(meta.get("timestamp"))

        git_sha_value = row.get("git_sha") or commit
        if meta and meta.get("git_sha"):
            git_sha_value = str(meta.get("git_sha"))

        git_branch_value = row.get("git_branch", "")
        if meta and meta.get("git_branch"):
            git_branch_value = str(meta.get("git_branch"))

        repo_dirty_value = row.get("repo_dirty") or ("true" if repo_dirty else "false")

        exp_id_value = row.get("exp_id", "")
        if meta and meta.get("exp_id"):
            exp_id_value = str(meta.get("exp_id"))

        if meta and meta.get("mode"):
            mode = normalize_mode(str(meta.get("mode")))
        else:
            mode = normalize_mode(mode_hint or row.get("mode"))

        trials_value: Optional[str] = row.get("trials")
        if meta and meta.get("trials") is not None:
            meta_trials = meta.get("trials")
            try:
                trials_value = str(int(meta_trials))
            except (TypeError, ValueError):
                trials_value = str(meta_trials)
        if not trials_value:
            trials_value = str(trials)

        python_version_value = row.get("python_version", "")
        if meta and meta.get("python_version"):
            python_version_value = str(meta.get("python_version"))
        elif not python_version_value:
            python_version_value = default_python_version

        packages_value = row.get("packages", "")
        if meta and meta.get("packages") is not None:
            packages_meta = meta.get("packages")
            if isinstance(packages_meta, dict):
                packages_value = json.dumps(packages_meta, sort_keys=True)
            else:
                packages_value = str(packages_meta)

        seeds_value = row.get("seeds", "")
        if meta and meta.get("seeds") is not None:
            seeds_meta = meta.get("seeds")
            if isinstance(seeds_meta, (list, tuple)):
                seeds_value = ",".join(str(item) for item in seeds_meta)
            else:
                seeds_value = str(seeds_meta)

        row.update(
            {
                "timestamp": timestamp,
                "run_id": row.get("run_id") or run_id,
                "git_sha": git_sha_value,
                "git_branch": git_branch_value,
                "repo_dirty": repo_dirty_value,
                "exp": exp,
                "exp_id": exp_id_value,
                "seed": seed,
                "mode": mode,
                "trials": str(trials_value),
                "successes": str(successes),
                "asr": f"{asr:.6f}",
                "python_version": python_version_value,
                "packages": packages_value,
                "seeds": seeds_value,
                "path": path.as_posix(),
            }
        )
        rows[key] = {column: row.get(column, "") for column in SUMMARY_COLUMNS}
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

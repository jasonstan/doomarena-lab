import argparse
import csv
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from taubench_airline_da import load_config, run as shim_run

try:
    from taubench_airline_da_real import run_real as real_run
except Exception:  # pragma: no cover - optional dependency
    real_run = None


SUMMARY_COLUMNS = [
    "timestamp",
    "run_id",
    "git_sha",
    "repo_dirty",
    "exp",
    "seed",
    "mode",
    "trials",
    "successes",
    "asr",
    "py_version",
    "path",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch DoomArena runs")
    parser.add_argument("--exp", default="airline_escalating_v1", help="Experiment name")
    parser.add_argument(
        "--seeds",
        default="42",
        help="Comma-separated list of seeds (e.g. \"41,42,43\")",
    )
    parser.add_argument("--trials", type=int, default=5, help="Trials per run")
    parser.add_argument(
        "--mode",
        choices=("SHIM", "REAL"),
        default="SHIM",
        help="Execution mode",
    )
    parser.add_argument(
        "--outdir",
        default="results",
        help="Base directory for experiment outputs",
    )
    return parser.parse_args()


def parse_seed_list(raw: str) -> List[int]:
    seeds: List[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if not chunk.isdigit():
            raise ValueError(f"Invalid seed value: {chunk}")
        seeds.append(int(chunk))
    if not seeds:
        raise ValueError("At least one seed must be provided")
    return seeds


def git_sha() -> str:
    return (
        subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True)
        .strip()
    )


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


def ensure_output_config(cfg: Dict, output_path: Path) -> Dict:
    output_cfg = dict(cfg.get("output", {}) or {})
    output_cfg["dir"] = output_path.parent.as_posix()
    output_cfg["file"] = output_path.name
    cfg["output"] = output_cfg
    return cfg


def load_summary_line(jsonl_path: Path) -> Dict:
    summary: Dict | None = None
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("event") == "summary":
                summary = data
    if summary is None:
        raise RuntimeError(f"Summary not found in {jsonl_path}")
    return summary


def parse_metrics(summary: Dict) -> Tuple[int, int, float]:
    trials = int(summary.get("trials", 0))
    successes = int(summary.get("successes", 0))
    if trials < successes:
        successes = trials
    asr = summary.get("asr")
    if asr is None:
        asr = successes / trials if trials else 0.0
    asr_value = float(asr)
    if asr_value < 0.0:
        asr_value = 0.0
    elif asr_value > 1.0:
        asr_value = 1.0
    return trials, successes, asr_value


def read_existing_summary(summary_path: Path) -> List[Dict[str, str]]:
    if not summary_path.exists():
        return []
    with summary_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return []
        if reader.fieldnames != SUMMARY_COLUMNS:
            # Legacy schema; start fresh
            return []
        return [dict(row) for row in reader]


def _seed_key(value: str) -> Union[int, str]:
    if value and value.isdigit():
        return int(value)
    return value


def upsert_summary_row(
    rows: List[Dict[str, str]],
    row: Dict[str, str],
) -> List[Dict[str, str]]:
    updated = False
    for existing in rows:
        if existing.get("exp") == row.get("exp") and existing.get("seed") == row.get("seed"):
            existing.update(row)
            updated = True
            break
    if not updated:
        rows.append(row)
    rows.sort(
        key=lambda item: (item.get("exp", ""), _seed_key(item.get("seed", "")))
    )
    return rows


def write_summary(summary_path: Path, rows: List[Dict[str, str]]) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        for row in rows:
            payload = {column: row.get(column, "") for column in SUMMARY_COLUMNS}
            writer.writerow(payload)


def run_single(
    exp: str,
    seed: int,
    trials: int,
    mode: str,
    outdir: Path,
    rows: List[Dict[str, str]],
    commit: str,
    run_id: str,
    repo_dirty: bool,
) -> None:
    config_path = Path("configs") / exp / "run.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    cfg = load_config(str(config_path))
    cfg["seed"] = seed
    cfg["trials"] = trials
    cfg["mode"] = mode

    output_dir = outdir / exp
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{exp}_seed{seed}.jsonl"
    ensure_output_config(cfg, output_path)

    actual_mode = mode
    if mode == "REAL":
        try:  # pragma: no cover - requires external dependency
            import tau_bench  # type: ignore
        except Exception as exc:
            print(f"tau_bench unavailable ({exc}); falling back to SHIM mode")
            actual_mode = "SHIM"
            shim_run(cfg)
        else:
            if real_run is None:
                print("REAL mode requested but real runner unavailable; using SHIM")
                actual_mode = "SHIM"
                shim_run(cfg)
            else:
                real_run(cfg)
    else:
        shim_run(cfg)

    summary = load_summary_line(output_path)
    trials_count, successes, asr = parse_metrics(summary)

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "git_sha": commit,
        "repo_dirty": "true" if repo_dirty else "false",
        "exp": exp,
        "seed": str(seed),
        "mode": actual_mode,
        "trials": str(trials_count),
        "successes": str(successes),
        "asr": f"{asr:.6f}",
        "py_version": platform.python_version(),
        "path": output_path.as_posix(),
    }

    upsert_summary_row(rows, row)
    print(
        f"{exp} seed={seed} mode={actual_mode} -> {successes}/{trials_count}"
        f" (ASR={asr:.3f})"
    )


def main() -> None:
    args = parse_args()
    try:
        seeds = parse_seed_list(args.seeds)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    outdir = Path(args.outdir)
    summary_path = Path("results") / "summary.csv"
    existing_rows = read_existing_summary(summary_path)
    commit = git_sha()
    run_id = generate_run_id()
    repo_dirty = repo_is_dirty()

    for seed in seeds:
        run_single(
            exp=args.exp,
            seed=seed,
            trials=args.trials,
            mode=args.mode,
            outdir=outdir,
            rows=existing_rows,
            commit=commit,
            run_id=run_id,
            repo_dirty=repo_dirty,
        )

    write_summary(summary_path, existing_rows)


if __name__ == "__main__":
    main()

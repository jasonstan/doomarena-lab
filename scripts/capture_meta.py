"""Utilities for capturing experiment metadata alongside results."""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

try:  # Python 3.8+
    from importlib import metadata as importlib_metadata
except ImportError:  # pragma: no cover - Python <3.8 fallback
    import importlib_metadata  # type: ignore

PACKAGE_LOOKUP: Mapping[str, str] = {
    "doomarena": "doomarena",
    "doomarena_taubench": "doomarena-taubench",
    "tau_bench": "tau-bench",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git_command(args: Sequence[str]) -> str:
    try:
        return (
            subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL, text=True)
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _git_sha() -> str:
    return _run_git_command(["rev-parse", "--short", "HEAD"])


def _git_branch() -> str:
    return _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])


def _detect_packages() -> dict[str, str]:
    versions: dict[str, str] = {}
    for logical_name, dist_name in PACKAGE_LOOKUP.items():
        try:
            versions[logical_name] = importlib_metadata.version(dist_name)
        except importlib_metadata.PackageNotFoundError:
            versions[logical_name] = "n/a"
    return versions


def normalize_seeds(seeds: Iterable[object]) -> list[object]:
    normalized: list[object] = []
    seen: set[str] = set()
    for seed in seeds:
        if seed is None:
            continue
        if isinstance(seed, int) and not isinstance(seed, bool):
            value: object = int(seed)
        else:
            text = str(seed).strip()
            if not text:
                continue
            try:
                value = int(text)
            except ValueError:
                value = text
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value)
    return normalized


def gather_metadata(
    *, exp_id: str, seeds: Iterable[object], trials: int, mode: str
) -> dict[str, object]:
    normalized_seeds = normalize_seeds(seeds)
    metadata: dict[str, object] = {
        "exp_id": exp_id,
        "timestamp": _now_iso(),
        "seeds": normalized_seeds,
        "trials": int(trials),
        "mode": str(mode).upper(),
        "git_sha": _git_sha(),
        "git_branch": _git_branch(),
        "python_version": platform.python_version(),
        "packages": _detect_packages(),
    }
    return metadata


def write_meta(
    exp_dir: Path | str,
    *,
    exp_id: str,
    seeds: Iterable[object],
    trials: int,
    mode: str,
) -> dict[str, object]:
    target_dir = Path(exp_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    metadata = gather_metadata(exp_id=exp_id, seeds=seeds, trials=trials, mode=mode)
    meta_path = target_dir / "meta.json"
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata


def _parse_seeds_argument(value: str | None) -> list[object]:
    if not value:
        return []
    parts = [part.strip() for part in value.split(",")]
    return [part for part in parts if part]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture experiment metadata next to results.")
    parser.add_argument(
        "--exp-dir",
        required=True,
        help="Experiment directory (relative to --results-root) where meta.json will be written.",
    )
    parser.add_argument("--exp-id", required=True, help="Unique experiment identifier.")
    parser.add_argument("--trials", required=True, type=int, help="Number of trials for the run.")
    parser.add_argument("--mode", default="SHIM", help="Execution mode for the run (e.g. SHIM or REAL).")
    parser.add_argument(
        "--seeds",
        default="",
        help="Comma-separated list of seeds associated with the experiment run.",
    )
    parser.add_argument(
        "--results-root",
        default="results",
        help="Base directory that contains experiment result folders.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional explicit output directory. Overrides --results-root/--exp-dir when provided.",
    )
    args = parser.parse_args(argv)

    if args.output:
        exp_dir = Path(args.output)
    else:
        exp_dir = Path(args.results_root) / args.exp_dir

    metadata = write_meta(
        exp_dir,
        exp_id=args.exp_id,
        seeds=_parse_seeds_argument(args.seeds),
        trials=args.trials,
        mode=args.mode,
    )
    meta_path = Path(exp_dir) / "meta.json"
    print(meta_path.as_posix())
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())

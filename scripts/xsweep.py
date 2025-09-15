#!/usr/bin/env python3
"""Run each seed listed in a YAML config via ``run_experiment.py``."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

import yaml


def _default_trials() -> int | None:
    raw = os.environ.get("TRIALS")
    if raw is None or not raw.strip():
        return None
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f"Invalid TRIALS value: {raw!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run configured seeds sequentially")
    parser.add_argument("--config", required=True, help="Path to experiment YAML config")
    parser.add_argument(
        "--mode",
        default=os.environ.get("MODE"),
        help="Override execution mode (defaults to config or $MODE)",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=_default_trials(),
        help="Override trials count (defaults to config or $TRIALS)",
    )
    return parser.parse_args()


def _load_config(path: str) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise SystemExit(f"Config not found: {path}")
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _ensure_int_seeds(raw_seeds: Iterable[object]) -> List[int]:
    seeds: List[int] = []
    for value in raw_seeds:
        try:
            seeds.append(int(value))
        except (TypeError, ValueError):
            print(f"xsweep: skipping invalid seed {value!r}", file=sys.stderr)
    return seeds


def _python_binary() -> str:
    candidates = [
        Path(".venv") / "bin" / "python",
        Path(".venv") / "Scripts" / "python.exe",
        Path(".venv") / "Scripts" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.as_posix()
    return sys.executable


def main() -> int:
    args = parse_args()
    cfg = _load_config(args.config)

    raw_seeds = cfg.get("seeds") or []
    if isinstance(raw_seeds, (str, bytes)):
        raw_seeds = [raw_seeds]
    seeds = _ensure_int_seeds(raw_seeds)
    if not seeds:
        print("xsweep: no seeds in config; nothing to run")
        return 0

    python_bin = _python_binary()
    rc = 0
    for seed in seeds:
        cmd = [
            python_bin,
            "scripts/run_experiment.py",
            "--config",
            args.config,
            "--seed",
            str(seed),
        ]
        if args.trials is not None:
            cmd.extend(["--trials", str(args.trials)])
        if args.mode:
            cmd.extend(["--mode", str(args.mode)])

        print("xsweep:", " ".join(shlex.quote(part) for part in cmd))
        completed = subprocess.run(cmd, check=False)
        rc |= completed.returncode
    return rc


if __name__ == "__main__":
    sys.exit(main())

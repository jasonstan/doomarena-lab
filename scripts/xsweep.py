#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

import yaml

DEFAULT_MODE = "SHIM"
DEFAULT_TRIALS = 5
SCRIPT_DIR = Path(__file__).resolve().parent
RUN_EXPERIMENT = SCRIPT_DIR / "run_experiment.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all seeds from an experiment config")
    parser.add_argument("--config", required=True, help="Path to experiment YAML config")
    parser.add_argument(
        "--mode",
        default=None,
        help="Execution mode override to pass to run_experiment.py",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=None,
        help="Number of trials override to pass to run_experiment.py",
    )
    return parser.parse_args()


def _resolve_mode(explicit_mode: str | None) -> str:
    if explicit_mode:
        return str(explicit_mode)
    return os.environ.get("MODE", DEFAULT_MODE)


def _resolve_trials(explicit_trials: int | None) -> int:
    if explicit_trials is not None:
        return int(explicit_trials)
    env_value = os.environ.get("TRIALS")
    if env_value is None:
        return DEFAULT_TRIALS
    try:
        return int(env_value)
    except ValueError as exc:
        raise SystemExit(f"Invalid TRIALS value: {env_value!r}") from exc


def _load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _extract_seeds(raw_seeds: Iterable[int | str] | int | str | None) -> List[int]:
    if raw_seeds is None:
        return []
    if isinstance(raw_seeds, (list, tuple)):
        items = list(raw_seeds)
    else:
        items = [raw_seeds]
    seeds: List[int] = []
    for item in items:
        if item in (None, ""):
            continue
        try:
            seeds.append(int(item))
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"Invalid seed value: {item!r}") from exc
    return seeds


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    cfg = _load_config(config_path)
    seeds = _extract_seeds(cfg.get("seeds"))
    if not seeds:
        print("xsweep: no seeds in config; nothing to run")
        return 0

    mode = _resolve_mode(args.mode)
    trials = _resolve_trials(args.trials)

    rc = 0
    for seed in seeds:
        cmd = [
            sys.executable,
            RUN_EXPERIMENT.as_posix(),
            "--config",
            config_path.as_posix(),
            "--seed",
            str(seed),
            "--trials",
            str(trials),
            "--mode",
            str(mode),
        ]
        print("xsweep:", " ".join(cmd))
        rc |= subprocess.call(cmd)
    return rc


if __name__ == "__main__":
    sys.exit(main())

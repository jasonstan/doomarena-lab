#!/usr/bin/env python3
"""Run each seed listed in a YAML config via ``run_experiment.py``."""
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
RUN_EXPERIMENT = SCRIPT_DIR / "run_experiment.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run configured seeds sequentially")
    parser.add_argument("--config", required=True, help="Path to experiment YAML config")
    parser.add_argument(
        "--seeds",
        default=None,
        help="Comma-separated seed overrides (defaults to config seeds)",
    )
    parser.add_argument(
        "--mode",
        default=None,
        help="Execution mode override passed to run_experiment.py",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=None,
        help="Trials override passed to run_experiment.py",
    )
    parser.add_argument(
        "--exp",
        default=None,
        help="Experiment name override passed to run_experiment.py",
    )
    parser.add_argument(
        "--outdir",
        default="results",
        help="Directory where per-seed outputs should be written",
    )
    return parser.parse_args()


def _load_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Config not found: {path}")
    with path.open("r") as handle:
        return yaml.safe_load(handle) or {}


def _coerce_seeds(raw: Iterable[int | str] | int | str | None) -> List[int]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        items = list(raw)
    else:
        items = [raw]
    seeds: List[int] = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        try:
            seeds.append(int(text))
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"Invalid seed value: {item!r}") from exc
    return seeds


def _resolve_seeds(arg: str | None, cfg: dict) -> List[int]:
    if arg:
        parts = [segment.strip() for segment in arg.split(",")]
        return _coerce_seeds([part for part in parts if part])
    return _coerce_seeds(cfg.get("seeds"))


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    cfg = _load_config(config_path)

    seeds = _resolve_seeds(args.seeds, cfg)
    if not seeds:
        print("xsweep: no seeds in config; nothing to run")
        return 0

    outdir = Path(args.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)

    rc = 0
    for seed in seeds:
        cmd = [
            sys.executable,
            RUN_EXPERIMENT.as_posix(),
            "--config",
            config_path.as_posix(),
            "--seed",
            str(seed),
        ]
        cmd.extend(["--outdir", outdir.as_posix()])
        if args.trials is not None:
            cmd.extend(["--trials", str(int(args.trials))])
        if args.mode:
            cmd.extend(["--mode", str(args.mode)])
        if args.exp:
            cmd.extend(["--exp", str(args.exp)])

        print("xsweep:", " ".join(shlex.quote(part) for part in cmd))
        completed = subprocess.run(cmd, check=False)
        rc |= completed.returncode

    return rc


if __name__ == "__main__":
    sys.exit(main())

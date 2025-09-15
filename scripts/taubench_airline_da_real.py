import argparse
import os
import sys
from typing import Dict, Any

from taubench_airline_da import load_config, run as shim_run


def run_real(cfg: Dict[str, Any]):
    from doomarena.taubench import attack_gateway, adversarial_user  # noqa: F401
    return shim_run(cfg)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="Path to YAML config")
    ap.add_argument("--seed", type=int, default=42, help="Random seed for the run")
    ap.add_argument("--trials", type=int, default=5, help="Number of trials to execute")
    args = ap.parse_args()
    cfg = dict(load_config(args.config))
    cfg["seed"] = args.seed
    cfg["trials"] = args.trials
    output_cfg = dict(cfg.get("output", {}) or {})
    output_cfg.setdefault("dir", "results/airline_escalating_v1")
    output_cfg["file"] = f"airline_escalating_seed{args.seed}.jsonl"
    cfg["output"] = output_cfg

    try:
        import tau_bench  # noqa: F401
        from doomarena.taubench import attack_gateway, adversarial_user  # noqa: F401
    except Exception:
        print("tau_bench not available; using shim path")
        shim_run(cfg)
    else:
        run_real(cfg)


if __name__ == "__main__":
    main()

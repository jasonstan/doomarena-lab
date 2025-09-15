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
    args = ap.parse_args()
    cfg = load_config(args.config)

    try:
        import tau_bench  # noqa: F401
        from doomarena.taubench import attack_gateway, adversarial_user  # noqa: F401
    except Exception:
        print("tau_bench not available; using shim path")
        cfg = dict(cfg)
        cfg["trials"] = 5
        shim_run(cfg)
    else:
        run_real(cfg)


if __name__ == "__main__":
    main()

import argparse, glob, os, subprocess, sys
from pathlib import Path


def run(cmd):
    print("+", " ".join(cmd), flush=True)
    return subprocess.call(cmd)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--glob", default=os.getenv("CONFIG_GLOB", "configs/*/run.yaml"))
    p.add_argument("--seeds", default=os.getenv("SEEDS", "41,42,43"))
    p.add_argument("--trials", type=int, default=int(os.getenv("TRIALS", "5")))
    p.add_argument("--mode", default=os.getenv("MODE", "SHIM"))
    p.add_argument("--exp", default=None, help="limit to a single exp name (dir name under configs/)")
    p.add_argument("--outdir", default=os.getenv("RUN_DIR", "results"), help="Output directory for run artifacts")
    args = p.parse_args()

    cfgs = sorted(glob.glob(args.glob))
    if args.exp:
        cfgs = [c for c in cfgs if Path(c).parent.name == args.exp]

    xsweep = Path("scripts/xsweep.py")
    rc = 0
    outdir = Path(args.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)

    for cfg in cfgs:
        exp = Path(cfg).parent.name
        if xsweep.exists():
            cmd = [
                sys.executable, "scripts/xsweep.py",
                "--config", cfg,
                "--seeds", args.seeds,
                "--trials", str(args.trials),
                "--mode", args.mode,
                "--exp", exp,
                "--outdir", outdir.as_posix(),
            ]
            rc |= run(cmd)
        else:
            # Fallback: loop seeds with run_experiment.py
            for s in [x for x in args.seeds.split(",") if x]:
                cmd = [
                    sys.executable, "scripts/run_experiment.py",
                    "--config", cfg,
                    "--seed", s,
                    "--trials", str(args.trials),
                    "--mode", args.mode,
                    "--exp", exp,
                    "--outdir", outdir.as_posix(),
                ]
                rc |= run(cmd)
    sys.exit(rc)


if __name__ == "__main__":
    main()

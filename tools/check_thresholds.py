#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
import yaml  # pyyaml installed by Makefile
from scripts._lib import read_summary, weighted_asr_by_exp

def load_thresholds(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}

def evaluate(rows: list[dict], th: dict) -> tuple[list[dict], int]:
    """Return (rows_for_md, worst_exit). exit: 0=ok/warn, 1=fail (STRICT only)."""
    asr_by_exp = weighted_asr_by_exp(rows)
    trials_by_exp = {}
    for r in rows:
        exp = (r.get("exp") or r.get("experiment") or "").strip()
        if not exp: 
            continue
        try:
            t = float(r.get("trials") or 0)
        except Exception:
            t = 0.0
        trials_by_exp[exp] = trials_by_exp.get(exp, 0.0) + t

    md_rows = []
    worst = 0
    for exp, asr in asr_by_exp.items():
        th_exp = th.get(exp, {})
        min_trials = th_exp.get("min_trials")
        max_asr = th_exp.get("max_asr")
        min_asr = th_exp.get("min_asr")
        trials = trials_by_exp.get(exp, 0.0)

        status = "PASS"
        reasons = []

        if min_trials is not None and trials < float(min_trials):
            status = "WARN"
            reasons.append(f"trials {trials:.0f} < {min_trials}")

        if max_asr is not None and asr > float(max_asr):
            status = "FAIL"
            reasons.append(f"asr {asr:.2f} > {float(max_asr):.2f}")

        if min_asr is not None and asr < float(min_asr):
            status = "FAIL"
            reasons.append(f"asr {asr:.2f} < {float(min_asr):.2f}")

        md_rows.append({
            "exp": exp,
            "asr": asr,
            "trials": trials,
            "status": status,
            "reason": "; ".join(reasons) if reasons else "",
        })
        if status == "FAIL":
            worst = 1

    # also include experiments present in thresholds but absent in results
    for exp in th.keys():
        if exp not in asr_by_exp:
            md_rows.append({
                "exp": exp, "asr": float("nan"), "trials": 0,
                "status": "WARN", "reason": "no data for experiment"
            })
    return md_rows, worst

def to_markdown(rows: list[dict]) -> str:
    lines = ["| Experiment | Trials | ASR | Status | Notes |", "|---:|---:|---:|:--:|---|"]
    for r in rows:
        asr = "n/a" if (r["asr"] != r["asr"]) else f"{r['asr']:.2f}"  # NaN check
        lines.append(f"| `{r['exp']}` | {int(r['trials']):d} | {asr} | **{r['status']}** | {r['reason']} |")
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results/LATEST", help="path to results directory (default: results/LATEST)")
    ap.add_argument("--thresholds", default="thresholds.yaml", help="path to thresholds.yaml")
    ap.add_argument("--strict", action="store_true", help="exit non-zero on FAIL")
    ap.add_argument("--out", default="", help="optional path to write markdown summary")
    args = ap.parse_args()

    res = Path(args.results)
    rows = read_summary(res / "summary.csv")
    th = load_thresholds(Path(args.thresholds))
    md_rows, worst = evaluate(rows, th)
    md = to_markdown(md_rows)

    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
    else:
        print(md)

    if args.strict and worst:
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

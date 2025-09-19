# Lightweight shared helpers for DoomArena-Lab scripts.
# Pure Python, no extra deps. Keep this tiny and stable.
from __future__ import annotations
import csv, subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

# --- filesystem/meta -----------------------------------------------------

def ensure_dir(p: Path | str) -> Path:
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    return p


def git_info() -> Dict[str, str]:
    def run(args: List[str]) -> str:
        try:
            out = subprocess.check_output(args, stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            out = ""
        return out

    sha = run(["git", "rev-parse", "--short", "HEAD"])
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return {"sha": sha, "branch": branch}


# --- csv reading / normalization ----------------------------------------

def _lower_keys(d: Dict[str, str]) -> Dict[str, str]:
    return {(k or "").strip().lower(): v for k, v in (d or {}).items()}


def read_summary(csv_path: Path | str) -> List[Dict[str, str]]:
    """Read summary.csv with case-insensitive headers; returns list of dicts (lower-cased keys)."""

    p = Path(csv_path)
    if not p.exists():
        return []
    rows: List[Dict[str, str]] = []
    with p.open(newline="") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            rows.append(_lower_keys(r))
    return rows


# --- metrics -------------------------------------------------------------

def weighted_asr_by_exp(rows: Iterable[Dict[str, str]]) -> Dict[str, float]:
    """
    Compute trial-weighted ASR per exp from rows that have at least exp & trials & successes.
    Falls back to 'attack_success_rate' or 'asr' if provided and numeric.
    """

    acc: Dict[str, Tuple[float, float]] = {}  # exp -> (successes_sum, trials_sum)
    for r in rows:
        exp = (r.get("exp") or r.get("experiment") or "").strip()
        if not exp:
            continue
        # Trials/successes preferred if present
        trials = r.get("trials")
        succ = r.get("successes") or r.get("success")
        try:
            if trials is not None and succ is not None:
                t = float(trials)
                s = float(succ)
                if t > 0:
                    S, T = acc.get(exp, (0.0, 0.0))
                    acc[exp] = (S + s, T + t)
                continue
        except Exception:
            pass
        # Otherwise fall back to asr/attack_success_rate * trials=1
        asr = r.get("asr") or r.get("attack_success_rate")
        try:
            a = float(asr)
            S, T = acc.get(exp, (0.0, 0.0))
            acc[exp] = (S + a, T + 1.0)
        except Exception:
            # skip if unusable
            pass
    out: Dict[str, float] = {}
    for exp, (S, T) in acc.items():
        out[exp] = (S / T) if T > 0 else 0.0
    return out


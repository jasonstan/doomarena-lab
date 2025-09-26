#!/usr/bin/env python3
"""
Richer, layout-agnostic HTML report writer.
Works with either:
  • legacy: results/<RUN_ID>/{summary_index.json, <exp>/rows.jsonl}
  • current: results/<RUN_ID>/{summary.csv, summary.svg, run.json[, rows.jsonl]}
Also tolerates rows.jsonl living under a child directory (e.g., <exp>/rows.jsonl).
"""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, Optional, Dict, Any, List, Tuple

try:
    from tools.report.html_report import ReportContext, TrialRecord, render_report
except ModuleNotFoundError:  # pragma: no cover - fallback when executed as a script
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.append(str(repo_root))
    from tools.report.html_report import ReportContext, TrialRecord, render_report

RunDir = Path


def resolve_run_dir(requested: Path) -> Path:
    """Resolve the run directory, following LATEST.path pointers when needed."""

    requested = Path(requested)

    try:
        resolved = requested.resolve(strict=False)
    except Exception:
        resolved = requested

    if resolved.exists():
        return resolved

    pointer = requested.parent / f"{requested.name}.path"
    if pointer.exists():
        try:
            target_text = pointer.read_text(encoding="utf-8").strip()
        except Exception:
            target_text = ""
        if target_text:
            target = Path(target_text)
            if not target.is_absolute():
                target = (pointer.parent / target).resolve()
            return target

    return resolved

# -------------- helpers --------------
def find_first(base: Path, names: Iterable[str]) -> Optional[Path]:
    for n in names:
        p = base / n
        if p.exists():
            return p
    return None

def find_glob_first(base: Path, patterns: Iterable[str]) -> Optional[Path]:
    for pat in patterns:
        for p in base.rglob(pat):
            if p.is_file():
                return p
    return None

def read_json(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def read_jsonl(path: Optional[Path], limit: int | None = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path or not path.exists():
        return rows
    try:
        with path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if limit is not None and i >= limit:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    # tolerate malformed lines
                    continue
    except Exception:
        pass
    return rows

def read_summary_csv(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if not path or not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            first = next(reader, None)
            return first
    except Exception:
        return None

def coerce_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

def coerce_int(x: Any) -> Optional[int]:
    try:
        return int(x)
    except Exception:
        return None

# -------------- data extraction --------------
@dataclass
class Meta:
    model: Optional[str] = None
    seed: Optional[int] = None
    trials: Optional[int] = None
    started_at: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

def extract_meta(run_dir: RunDir) -> Meta:
    # Prefer top-level run.json; fallback to any nested run.json
    run_json = find_first(run_dir, ["run.json"]) or find_glob_first(run_dir, ["*/run.json"])
    meta = Meta()
    data = read_json(run_json) or {}
    meta.raw = data if isinstance(data, dict) else {}
    # Common places
    meta.model = (
        data.get("provider", {}).get("model")
        or data.get("model")
        or data.get("config", {}).get("model")
    )
    meta.seed = (
        data.get("seed")
        or data.get("rng_seed")
        or data.get("config", {}).get("seed")
        or data.get("config", {}).get("rng_seed")
    )
    meta.trials = data.get("trials") or data.get("config", {}).get("trials")
    meta.started_at = data.get("started_at") or data.get("ts") or data.get("time")
    # Fallback: from summary.csv
    if meta.trials is None:
        row = read_summary_csv(run_dir / "summary.csv")
        if row:
            meta.trials = coerce_int(row.get("trials") or row.get("n") or row.get("count"))
    return meta

def compute_asr(run_dir: RunDir, summary_row: Optional[Dict[str, Any]]) -> Optional[float]:
    # 1) CSV explicitly carries asr
    if summary_row:
        for key in ("asr", "ASR", "pass_rate", "success_rate"):
            if key in summary_row and summary_row[key] not in (None, ""):
                v = coerce_float(summary_row[key])
                if v is not None:
                    return v
        # or successes / trials
        succ = coerce_int(summary_row.get("successes") or summary_row.get("success"))
        trials = coerce_int(summary_row.get("trials") or summary_row.get("count"))
        if succ is not None and trials:
            return succ / max(trials, 1)
    # 2) derive from rows.jsonl
    rows = load_rows_anywhere(run_dir, limit=None)  # full read to compute
    if rows:
        ok = 0
        total = 0
        for r in rows:
            val = r.get("success")
            if isinstance(val, bool):
                ok += 1 if val else 0
                total += 1
            elif val in ("PASS", "SUCCESS", "OK", "True", "true", 1):
                ok += 1
                total += 1
            elif val in ("FAIL", "False", "false", 0):
                total += 1
        if total:
            return ok / total
    return None

def find_rows_path(run_dir: RunDir) -> Optional[Path]:
    return (
        find_first(run_dir, ["rows.jsonl", "rows.json"])
        or find_glob_first(run_dir, ["*/rows.jsonl", "*/*/rows.jsonl", "*/rows.json", "*/*/rows.json"])
    )


def load_rows_anywhere(run_dir: RunDir, limit: Optional[int] = 25) -> List[Dict[str, Any]]:
    # Prefer top-level rows.jsonl/rows.json; else any nested *rows.jsonl
    cand = find_rows_path(run_dir)
    if cand and cand.suffix == ".json":
        try:
            data = read_json(cand)
            if isinstance(data, list):
                return data[: limit or len(data)]
            return []
        except Exception:
            return []
    return read_jsonl(cand, limit=limit)

TRIAL_SAMPLE_LIMIT = 50


def sample_trial_rows(rows_path: Optional[Path], limit: int = TRIAL_SAMPLE_LIMIT) -> Tuple[List[TrialRecord], int]:
    if not rows_path or not rows_path.exists():
        return [], 0

    # Legacy runs may store a single JSON array (rows.json) instead of JSONL.
    if rows_path.suffix == ".json":
        try:
            payload = read_json(rows_path)
        except Exception:
            payload = None
        if isinstance(payload, list):
            total = 0
            records: List[TrialRecord] = []
            for entry in payload:
                if not isinstance(entry, dict):
                    continue
                total += 1
                if len(records) < limit:
                    records.append(TrialRecord(index=total, payload=entry))
            return records, total

    records = []
    total = 0
    try:
        with rows_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(payload, dict):
                    continue
                total += 1
                if len(records) < limit:
                    records.append(TrialRecord(index=total, payload=payload))
    except OSError:
        pass
    return records, total


def render_html(run_dir: RunDir) -> str:
    row_csv = read_summary_csv(run_dir / "summary.csv")
    meta = extract_meta(run_dir)
    asr = compute_asr(run_dir, row_csv)

    rows_path = find_rows_path(run_dir)
    trial_records, total_trials = sample_trial_rows(rows_path, TRIAL_SAMPLE_LIMIT)

    run_meta_payload: Dict[str, Any] = {}
    if meta.raw:
        run_meta_payload = meta.raw
    else:
        run_meta_payload = asdict(meta)

    context = ReportContext(
        run_dir=run_dir,
        run_meta=run_meta_payload,
        summary_row=row_csv,
        asr=asr,
        trial_records=trial_records,
        total_trials=total_trials,
        trial_limit=TRIAL_SAMPLE_LIMIT,
        rows_path=rows_path,
    )

    return render_report(context)

def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("usage: mk_report.py <RUN_DIR>", file=sys.stderr)
        return 2
    run_dir = resolve_run_dir(Path(argv[1]))
    run_dir.mkdir(parents=True, exist_ok=True)
    html = render_html(run_dir)
    (run_dir / "index.html").write_text(html, encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

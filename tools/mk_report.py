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
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Dict, Any, List, Tuple

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

def extract_meta(run_dir: RunDir) -> Meta:
    # Prefer top-level run.json; fallback to any nested run.json
    run_json = find_first(run_dir, ["run.json"]) or find_glob_first(run_dir, ["*/run.json"])
    meta = Meta()
    data = read_json(run_json) or {}
    # Common places
    meta.model = data.get("model") or data.get("config", {}).get("model")
    meta.seed = data.get("seed") or data.get("config", {}).get("seed")
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

def load_rows_anywhere(run_dir: RunDir, limit: Optional[int] = 25) -> List[Dict[str, Any]]:
    # Prefer top-level rows.jsonl/rows.json; else any nested *rows.jsonl
    cand = (
        find_first(run_dir, ["rows.jsonl", "rows.json"])
        or find_glob_first(run_dir, ["*/rows.jsonl", "*/*/rows.jsonl", "*/rows.json", "*/*/rows.json"])
    )
    if cand and cand.suffix == ".json":
        try:
            data = read_json(cand)
            if isinstance(data, list):
                return data[: limit or len(data)]
            return []
        except Exception:
            return []
    return read_jsonl(cand, limit=limit)

# -------------- HTML --------------
CSS = """
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Inter,Helvetica,Arial,sans-serif;line-height:1.45;margin:24px;}
  h1{margin:0 0 8px 0}
  .badges{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 16px}
  .badge{background:#f2f4f7;border:1px solid #e4e7ec;border-radius:999px;padding:4px 10px;font-size:12px}
  .kv{display:grid;grid-template-columns:120px 1fr;gap:6px;align-items:start;margin:8px 0 16px}
  .section{margin:24px 0}
  .muted{color:#667085}
  table{border-collapse:collapse;width:100%;margin-top:8px}
  th,td{border:1px solid #e4e7ec;padding:6px 8px;font-size:13px;vertical-align:top}
  th{background:#f8fafc;text-align:left}
  code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}
  .io{max-height:8.5em;overflow:auto;white-space:pre-wrap}
  img.summary{max-width:520px;width:100%;height:auto;border:1px solid #e4e7ec;border-radius:8px;background:#fff}
"""

def render_html(run_dir: RunDir) -> str:
    row_csv = read_summary_csv(run_dir / "summary.csv")
    meta = extract_meta(run_dir)
    asr = compute_asr(run_dir, row_csv)

    # Trial rows (first N)
    trials = load_rows_anywhere(run_dir, limit=25)

    # Pull candidate I/O fields
    def pick(d: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[str]:
        for k in keys:
            if k in d and d[k] not in (None, ""):
                v = d[k]
                return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        return None

    # Build table rows
    table_rows: List[str] = []
    for i, r in enumerate(trials):
        trial_id = r.get("trial_id") or r.get("idx") or i
        prompt = pick(r, ("input", "prompt", "attack_prompt", "user", "message"))
        output = pick(r, ("output", "response", "model", "assistant"))
        success = r.get("success")
        reason = r.get("reason") or r.get("judge_reason") or r.get("why")
        table_rows.append(
            "<tr>"
            f"<td>{trial_id}</td>"
            f"<td class='io'><pre>{html_escape(prompt or '')}</pre></td>"
            f"<td class='io'><pre>{html_escape(output or '')}</pre></td>"
            f"<td>{html_escape(str(success))}</td>"
            f"<td class='io'><pre>{html_escape(str(reason or ''))}</pre></td>"
            "</tr>"
        )

    # Summary SVG (if present)
    svg_tag = ""
    if (run_dir / "summary.svg").exists():
        svg_tag = "<img class='summary' src='summary.svg' alt='Summary chart'/>"

    # Badges
    badges = []
    if asr is not None:
        badges.append(f"<span class='badge'>ASR: {asr:.6g}</span>")
    if meta.model:
        badges.append(f"<span class='badge'>model: {html_escape(meta.model)}</span>")
    if meta.seed is not None:
        badges.append(f"<span class='badge'>seed: {meta.seed}</span>")
    if meta.trials is not None:
        badges.append(f"<span class='badge'>trials: {meta.trials}</span>")
    if meta.started_at:
        badges.append(f"<span class='badge'>started: {html_escape(str(meta.started_at))}</span>")
    badges_html = f"<div class='badges'>{''.join(badges)}</div>" if badges else ""

    # Trial table HTML
    table_html = (
        "<p class='muted'>No per-trial rows available.</p>"
        if not table_rows
        else (
            "<table><thead><tr>"
            "<th>#</th><th>Prompt</th><th>Model output</th><th>Success</th><th>Reason</th>"
            "</tr></thead><tbody>"
            + "".join(table_rows)
            + "</tbody></table>"
        )
    )

    # Artifact links (always)
    artifacts = []
    for name in ("summary.csv", "summary.svg", "run.json", "rows.jsonl"):
        p = run_dir / name
        if p.exists():
            artifacts.append(f"<li><a href='{name}'>{name}</a></li>")
    artifacts_html = "<ul>" + "".join(artifacts) + "</ul>" if artifacts else "<p class='muted'>None</p>"

    return f"""<!doctype html>
<meta charset="utf-8"/>
<title>DoomArena-Lab Report — {run_dir.name}</title>
<style>{CSS}</style>
<h1>DoomArena-Lab Report</h1>
<div class="muted">Run: {run_dir.name}</div>
{badges_html}

<div class="section">
  {svg_tag}
</div>

<div class="section">
  <h2>Trial I/O (first {len(table_rows)} rows)</h2>
  {table_html}
</div>

<div class="section">
  <h2>Artifacts</h2>
  {artifacts_html}
</div>
"""

def html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )

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

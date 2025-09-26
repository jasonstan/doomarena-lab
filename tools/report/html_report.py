from __future__ import annotations
import html, json
from pathlib import Path
from typing import Any, Dict, List, Tuple

def _esc(s: Any) -> str:
    return html.escape("" if s is None else str(s))

def _label_for_slice(row: Dict[str, Any]) -> str:
    return row.get("description") or row.get("exp_id") or row.get("id") or row.get("mode") or "slice"

def _series_from_json(data: Dict[str, Any]) -> List[Tuple[str, float]]:
    series = []
    slices = data.get("slices") or data.get("experiments") or []
    for s in slices:
        lbl = _label_for_slice(s)
        asr = float(s.get("asr") or s.get("callable_pass_rate") or 0.0)
        series.append((lbl, asr))
    if not series:
        series.append(("Results", float(data.get("callable_pass_rate") or 0.0)))
    return series

def _series_from_csv(rows: List[Dict[str, Any]]) -> List[Tuple[str, float]]:
    series = []
    for r in rows:
        lbl = r.get("description") or r.get("exp_id") or r.get("id") or "exp"
        asr = float(r.get("asr") or r.get("pass_rate") or r.get("success_rate") or 0.0)
        series.append((lbl, asr))
    if not series:
        series.append(("Results", 0.0))
    return series

def _read_rows_jsonl(run_dir: Path, limit: int = 50) -> List[Dict[str, Any]]:
    p = run_dir / "rows.jsonl"
    out: List[Dict[str, Any]] = []
    if not p.exists():
        return out
    with p.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= limit: break
            try:
                obj = json.loads(line)
            except Exception:
                continue
            out.append(obj)
    return out

def render_html(run_dir: Path, data: Dict[str, Any], mode: str = "json") -> str:
    # Header data (guarded)
    model = (data.get("model") or data.get("config", {}).get("model") or "unknown") if mode=="json" else (
            (data.get("csv_rows", [{}])[0].get("model") if data.get("csv_rows") else "unknown")
    )
    seed = str((data.get("seed") or data.get("meta", {}).get("seed") or "unknown") if mode=="json" else (
            (data.get("csv_rows", [{}])[0].get("seed") if data.get("csv_rows") else "unknown")
    ))

    # Series
    if mode == "json":
        series = _series_from_json(data)
    elif mode == "csv":
        series = _series_from_csv(data.get("csv_rows", []))
    else:
        series = [("No data", 0.0)]

    bars = "".join(
        f'<div style="display:flex;align-items:center;margin:6px 0;">'
        f'<div style="width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{_esc(lbl)}</div>'
        f'<div style="background:#e8ecf3;width:360px;height:16px;margin:0 8px 0 8px;">'
        f'<div style="background:#5b8def;height:16px;width:{min(max(val,0.0),1.0)*360:.0f}px"></div></div>'
        f'<div style="width:60px;text-align:right">{val:.0%}</div></div>'
        for lbl, val in series
    )

    # Trial I/O table (truncate for readability)
    trials = _read_rows_jsonl(run_dir, limit=50)
    if trials:
        trs = []
        for i, t in enumerate(trials, 1):
            inn = _esc(t.get("input", ""))[:160] + ("…" if len(_esc(t.get("input",""))) > 160 else "")
            out = _esc(t.get("output", ""))[:160] + ("…" if len(_esc(t.get("output",""))) > 160 else "")
            trs.append(f"<tr><td>{i}</td><td>{_esc(t.get('exp_id') or t.get('slice_id') or '—')}</td>"
                       f"<td>{_esc(t.get('attack_id') or '—')}</td><td><code>{inn}</code></td>"
                       f"<td><code>{out}</code></td><td>{'✔' if t.get('success') else '✖'}</td></tr>")
        io_table = (
            "<table><thead><tr><th>#</th><th>slice</th><th>attack</th><th>input</th><th>output</th><th>ok</th></tr></thead>"
            f"<tbody>{''.join(trs)}</tbody></table>"
            "<p>See full details in <code>rows.jsonl</code>.</p>"
        )
    else:
        io_table = "<p>No trial rows found.</p>"

    # HTML
    head = f"""<!doctype html><meta charset="utf-8">
<title>DoomArena-Lab Report — {_esc(run_dir.name)}</title>
<style>
  body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }}
  .badges span {{ display:inline-block; margin-right:10px; padding:4px 8px; border-radius:12px; background:#f0f0f0; }}
  h1 {{ margin-bottom: 8px; }}
  section {{ margin: 18px 0; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }}
  th {{ background: #fafafa; text-align: left; }}
</style>
<h1>DoomArena-Lab Run Report</h1>
<div class="badges">
  <span>Run: {_esc(run_dir.name)}</span>
  <span>Model: {_esc(model)}</span>
  <span>Seed: {_esc(seed)}</span>
</div>
"""
    chart = f"<section><h2>Attack results (ASR)</h2>{bars}</section>"
    gates = (
        "<section><h2>Governance decisions</h2>"
        "<p><em>pre</em> = before calling the model; <em>post</em> = after seeing model output.</p>"
        "</section>"
    )
    io = f"<section><h2>Trial I/O (first 50)</h2>{io_table}</section>"

    return head + chart + gates + io

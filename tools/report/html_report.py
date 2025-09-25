from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _safe(data: Any, *keys: str, default: str = "—") -> str:
    cur = data
    try:
        for key in keys:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(key, {})
        if cur in ({}, None, ""):
            return default
        return str(cur)
    except Exception:
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        text = str(value).strip()
        if not text:
            return default
        return int(float(text))
    except Exception:
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            return default
        if text.endswith("%"):
            return float(text[:-1]) / 100.0
        return float(text)
    except Exception:
        return default


def _label_for_slice(row: dict[str, Any]) -> str:
    return (
        row.get("description")
        or row.get("exp_id")
        or row.get("id")
        or row.get("mode")
        or "slice"
    )


def _collect_reason_sections(data: dict[str, Any]) -> str:
    reason_sources: dict[str, list[tuple[str, int]]] = {}

    grouped = data.get("reason_counts_by_decision")
    if isinstance(grouped, dict):
        for decision, payload in grouped.items():
            if isinstance(payload, dict) and payload:
                pairs = [
                    (str(reason), _as_int(count))
                    for reason, count in payload.items()
                ]
                reason_sources[str(decision)] = pairs

    if not reason_sources:
        flat = data.get("reason_counts")
        if isinstance(flat, dict) and flat:
            pairs = [(str(reason), _as_int(count)) for reason, count in flat.items()]
            reason_sources["all"] = pairs

    top = data.get("top_reasons")
    if isinstance(top, dict):
        for key, payload in top.items():
            pairs: list[tuple[str, int]] = []
            if isinstance(payload, dict):
                pairs = [(str(reason), _as_int(count)) for reason, count in payload.items()]
            elif isinstance(payload, list):
                for item in payload:
                    if isinstance(item, (list, tuple)) and item:
                        reason = str(item[0])
                        count = _as_int(item[1]) if len(item) > 1 else 0
                        pairs.append((reason, count))
            if pairs and str(key) not in reason_sources:
                reason_sources[str(key)] = pairs

    if not reason_sources:
        return "<p>No gate reasons recorded.</p>"

    blocks: list[str] = []
    for decision, pairs in reason_sources.items():
        if not pairs:
            continue
        pairs = sorted(pairs, key=lambda item: (-item[1], item[0]))
        rows = "".join(
            f"<li><span class='reason'>{html.escape(reason)}</span><span class='count'>{count}</span></li>"
            for reason, count in pairs
        )
        blocks.append(
            "<div class='reason-block'>"
            f"<h3>{html.escape(decision.title())}</h3>"
            f"<ul>{rows}</ul>"
            "</div>"
        )

    return "<div class='reason-grid'>" + "".join(blocks) + "</div>"


def render_html(run_dir: Path, data: dict[str, Any], *, mode: str = "json") -> str:
    run_dir = Path(run_dir)
    model = "unknown"
    seed = "unknown"
    totals = {}
    rows: list[dict[str, Any]] = []

    if mode == "json":
        totals = data.get("totals") if isinstance(data.get("totals"), dict) else {}
        model = (
            data.get("model")
            or _safe(data, "config", "model", default=model)
            or model
        )
        raw_seed = data.get("seed") or _safe(data, "meta", "seed", default=seed)
        seed = str(raw_seed or seed)
    elif mode == "csv":
        rows = data.get("csv_rows", []) if isinstance(data.get("csv_rows"), list) else []
        if rows:
            model = str(rows[0].get("model") or model)
            seed = str(rows[0].get("seed") or seed)
    else:
        totals = {}

    title = f"DoomArena-Lab Report — {html.escape(run_dir.name or run_dir.as_posix())}"
    head = f"""
<!doctype html>
<html lang='en'>
  <head>
    <meta charset='utf-8'>
    <title>{title}</title>
    <style>
      body {{ font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; margin: 24px; color: #0f172a; }}
      h1 {{ font-size: 28px; margin-bottom: 12px; }}
      h2 {{ margin-top: 32px; }}
      .badges span {{ display:inline-block; margin-right:10px; padding:4px 8px; border-radius:12px; background:#e2e8f0; }}
      .chart {{ max-width:640px; margin-top:24px; }}
      .bars {{ margin-top:12px; }}
      .bar-row {{ display:flex; align-items:center; margin:6px 0; }}
      .bar-label {{ width:200px; font-weight:500; }}
      .bar-track {{ background:#cbd5f5; width:360px; height:16px; border-radius:8px; overflow:hidden; }}
      .bar-fill {{ background:#5b8def; height:16px; border-radius:8px 0 0 8px; }}
      .bar-value {{ width:60px; text-align:right; margin-left:8px; font-variant-numeric: tabular-nums; }}
      table {{ border-collapse: collapse; width: 100%; max-width: 100%; }}
      th, td {{ border: 1px solid #e2e8f0; padding: 6px 8px; vertical-align: top; }}
      th {{ background: #f8fafc; text-align: left; }}
      code {{ background: #f1f5f9; padding: 2px 4px; border-radius: 4px; }}
      .reason-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:16px; margin-top:16px; }}
      .reason-block {{ background:#f8fafc; padding:12px 14px; border-radius:8px; box-shadow:0 1px 2px rgba(15,23,42,0.08); }}
      .reason-block h3 {{ margin:0 0 8px; font-size:14px; text-transform:uppercase; letter-spacing:0.05em; color:#475569; }}
      .reason-block ul {{ list-style:none; margin:0; padding:0; }}
      .reason-block li {{ display:flex; justify-content:space-between; padding:2px 0; font-size:14px; color:#0f172a; }}
      .reason-block .reason {{ font-weight:600; }}
      .gate-counts {{ list-style: none; padding: 0; margin: 12px 0 0; }}
      .gate-counts li {{ margin: 4px 0; }}
      .note {{ color:#475569; font-size:14px; margin-top:4px; }}
    </style>
  </head>
  <body>
    <h1>DoomArena-Lab Run Report</h1>
    <div class='badges'>
      <span>Run: {html.escape(run_dir.name or run_dir.as_posix())}</span>
      <span>Model: {html.escape(str(model))}</span>
      <span>Seed: {html.escape(str(seed))}</span>
    </div>
"""

    series: list[tuple[str, float]] = []
    chart_note = ""
    if mode == "json":
        slices = []
        for key in ("slices", "experiments", "runs"):
            payload = data.get(key)
            if isinstance(payload, list):
                slices = payload
                break
        for entry in slices:
            if not isinstance(entry, dict):
                continue
            label = _label_for_slice(entry)
            asr_value = _as_float(
                entry.get("asr")
                or entry.get("callable_pass_rate")
                or entry.get("pass_rate")
            )
            series.append((label, asr_value))
        if not series:
            rate = _as_float(data.get("callable_pass_rate") or data.get("asr"))
            series.append(("Results", rate))
    elif mode == "csv":
        rows = [row for row in rows if isinstance(row, dict)]
        for row in rows:
            label = row.get("description") or row.get("exp_id") or row.get("id") or "exp"
            rate = _as_float(
                row.get("asr")
                or row.get("pass_rate")
                or row.get("success_rate")
                or row.get("callable_pass_rate")
            )
            series.append((str(label), rate))
        if not series:
            chart_note = "<p class='note'>summary.csv did not contain pass rate columns.</p>"
    else:
        chart_note = "<p class='note'>No summary_index.json or summary.csv found; showing placeholder chart.</p>"
        series.append(("No data", 0.0))

    bars = "".join(
        "<div class='bar-row'>"
        f"<div class='bar-label'>{html.escape(label)}</div>"
        f"<div class='bar-track'><div class='bar-fill' style='width:{min(max(value, 0.0), 1.0) * 360:.0f}px'></div></div>"
        f"<div class='bar-value'>{value:.0%}</div>"
        "</div>"
        for label, value in series
    ) if series else "<p>No series data available.</p>"

    chart = f"""
    <section class='chart'>
      <h2>Attack results (ASR)</h2>
      {chart_note}
      <div class='bars'>{bars}</div>
    </section>
"""

    summary_lines: list[str] = []
    if isinstance(totals, dict) and totals:
        total_trials = _as_int(
            totals.get("rows")
            or totals.get("total_trials")
            or totals.get("trials")
        )
        callable_trials = _as_int(totals.get("callable") or totals.get("callable_trials"))
        passes = _as_int(totals.get("passes") or totals.get("passed") or totals.get("successes"))
        fails = _as_int(totals.get("fails") or totals.get("failed"))
        if total_trials:
            summary_lines.append(f"<li>Total trials: {total_trials}</li>")
        if callable_trials:
            summary_lines.append(f"<li>Callable trials: {callable_trials}</li>")
        if passes:
            summary_lines.append(f"<li>Successful trials: {passes}</li>")
        if fails:
            summary_lines.append(f"<li>Failed trials: {fails}</li>")
        overall_rate = _as_float(
            totals.get("asr")
            or totals.get("callable_pass_rate")
            or data.get("callable_pass_rate")
        )
        if overall_rate:
            summary_lines.append(f"<li>Callable pass rate: {overall_rate:.1%}</li>")

    summary_section = ""
    if summary_lines:
        summary_section = "<section><h2>Summary</h2><ul>" + "".join(summary_lines) + "</ul></section>"
    elif mode == "none":
        summary_section = "<section><h2>Summary</h2><p>No summary data available.</p></section>"

    gates = data.get("gates") if isinstance(data.get("gates"), dict) else {}
    pre_counts = gates.get("pre") if isinstance(gates.get("pre"), dict) else {}
    post_counts = gates.get("post") if isinstance(gates.get("post"), dict) else {}

    gate_lines: list[str] = []
    if pre_counts:
        gate_lines.append(
            "<li>pre allow/warn/deny: "
            f"{_as_int(pre_counts.get('allow'))}/"
            f"{_as_int(pre_counts.get('warn'))}/"
            f"{_as_int(pre_counts.get('deny'))}</li>"
        )
    if post_counts:
        gate_lines.append(
            "<li>post allow/warn/deny: "
            f"{_as_int(post_counts.get('allow'))}/"
            f"{_as_int(post_counts.get('warn'))}/"
            f"{_as_int(post_counts.get('deny'))}</li>"
        )
    gate_counts_html = "<ul class='gate-counts'>" + "".join(gate_lines) + "</ul>" if gate_lines else "<p>No gate counts recorded.</p>"
    reasons_html = _collect_reason_sections(data)
    gates_html = f"""
    <section>
      <h2>Governance decisions</h2>
      <p class='note'><em>pre</em> = before calling the model; <em>post</em> = after observing output.</p>
      {gate_counts_html}
      {reasons_html}
    </section>
"""

    trial_html = "<p>No trial rows found.</p>"
    rows_path = Path(run_dir) / "rows.jsonl"
    if rows_path.exists():
        entries: list[tuple[str, str, str, str, str, str]] = []
        with rows_path.open(encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if index >= 50:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                inp = html.escape(str(obj.get("input", "")))[:160]
                out = html.escape(str(obj.get("output", "")))[:160]
                if len(inp) == 160:
                    inp += "…"
                if len(out) == 160:
                    out += "…"
                entries.append(
                    (
                        str(obj.get("trial") or index + 1),
                        str(obj.get("exp_id") or obj.get("slice_id") or "—"),
                        str(obj.get("attack_id") or "—"),
                        inp,
                        out,
                        "✔" if obj.get("success") else "✖",
                    )
                )
        if entries:
            table_rows = "\n".join(
                "<tr>"
                f"<td>{trial}</td>"
                f"<td>{slice_id}</td>"
                f"<td>{attack}</td>"
                f"<td><code>{inp}</code></td>"
                f"<td><code>{out}</code></td>"
                f"<td>{status}</td>"
                "</tr>"
                for trial, slice_id, attack, inp, out, status in entries
            )
            trial_html = f"""
            <table>
              <thead><tr><th>#</th><th>slice</th><th>attack</th><th>input</th><th>output</th><th>ok</th></tr></thead>
              <tbody>{table_rows}</tbody>
            </table>
            <p>See full details in <code>rows.jsonl</code>.</p>
            """

    trials_section = f"""
    <section>
      <h2>Trial I/O (first 50)</h2>
      {trial_html}
    </section>
"""

    body = head + chart + summary_section + gates_html + trials_section + "\n  </body>\n</html>"
    return body

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple


TRUNCATE_CHARS = 280


@dataclass
class TrialRecord:
    """Minimal representation of a trial row used for HTML rendering."""

    index: int
    payload: Mapping[str, Any]


@dataclass
class ReportContext:
    """Structured payload consumed by :func:`render_report`."""

    run_dir: Path
    run_meta: Mapping[str, Any]
    summary_row: Optional[Mapping[str, Any]]
    asr: Optional[float]
    trial_records: Sequence[TrialRecord]
    total_trials: Optional[int]
    trial_limit: int
    rows_path: Optional[Path]


def render_report(ctx: ReportContext) -> str:
    """Render the full HTML report using contextual metadata and trial samples."""

    badges = _build_badges(ctx)
    chart_html = _render_chart(ctx)
    overview_html = _render_overview(ctx)
    reasons_html = _render_reasons(ctx)
    trial_table_html = _render_trial_table(ctx)
    artifacts_html = _render_artifacts(ctx)

    title = f"DoomArena-Lab Report — {html.escape(ctx.run_dir.name)}"

    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\"/>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>
    <title>{title}</title>
    <style>{_CSS}</style>
  </head>
  <body>
    <header class=\"page-header\">
      <h1>DoomArena-Lab Run Report</h1>
      <div class=\"meta\">
        <div>Run: {html.escape(ctx.run_dir.name)}</div>
        {badges}
      </div>
    </header>
    {overview_html}
    {chart_html}
    {reasons_html}
    <section>
      <h2>Trial I/O</h2>
      {trial_table_html}
    </section>
    <section>
      <h2>Artifacts</h2>
      {artifacts_html}
    </section>
    <script>{_SCRIPT}</script>
  </body>
</html>"""


def _build_badges(ctx: ReportContext) -> str:
    badges: List[str] = []

    model = _coalesce_model(ctx.run_meta)
    if model:
        badges.append(f"<span class=\"badge\">Model: {html.escape(model)}</span>")

    seed = _coalesce_seed(ctx.run_meta)
    badges.append(
        f"<span class=\"badge\">Seed: {html.escape(seed if seed is not None else 'n/a')}</span>"
    )

    if ctx.asr is not None:
        badges.append(f"<span class=\"badge\">ASR: {ctx.asr:.2%}</span>")

    trials = ctx.total_trials if ctx.total_trials is not None else len(ctx.trial_records)
    badges.append(f"<span class=\"badge\">Trials: {trials}</span>")

    return "".join(badges)


def _coalesce_model(meta: Mapping[str, Any]) -> Optional[str]:
    for path in (
        ("provider", "model"),
        ("model",),
        ("config", "model"),
    ):
        value = _dig(meta, path)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _coalesce_seed(meta: Mapping[str, Any]) -> Optional[str]:
    for path in (
        ("seed",),
        ("rng_seed",),
        ("config", "seed"),
        ("config", "rng_seed"),
    ):
        value = _dig(meta, path)
        if value is None:
            continue
        if isinstance(value, (int, float)):
            return str(int(value))
        return str(value)
    return None


def _render_chart(ctx: ReportContext) -> str:
    summary_json = ctx.run_dir / "summary_index.json"
    series: List[Tuple[str, float]] = []
    if summary_json.exists():
        try:
            payload = json.loads(summary_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, Mapping):
            series = _series_from_summary_index(payload)
    if not series and ctx.summary_row:
        label = ctx.summary_row.get("description") or ctx.summary_row.get("exp_id") or "Results"
        try:
            asr = float(ctx.summary_row.get("asr"))
        except (TypeError, ValueError):
            asr = 0.0
        series = [(str(label), max(0.0, min(asr, 1.0)))]

    if not series:
        return ""

    bars = "".join(
        (
            "<div class=\"bar-row\">"
            f"<div class=\"bar-label\">{html.escape(label)}</div>"
            f"<div class=\"bar-track\"><div class=\"bar-fill\" style=\"width:{value * 100:.1f}%\"></div></div>"
            f"<div class=\"bar-value\">{value:.1%}</div>"
            "</div>"
        )
        for label, value in series
    )

    return f"<section><h2>Attack results (ASR)</h2>{bars}</section>"


def _series_from_summary_index(data: Mapping[str, Any]) -> List[Tuple[str, float]]:
    series: List[Tuple[str, float]] = []
    slices = data.get("slices") or data.get("experiments") or []
    if isinstance(slices, Sequence):
        for item in slices:
            if not isinstance(item, Mapping):
                continue
            label = (
                item.get("description")
                or item.get("exp_id")
                or item.get("id")
                or "slice"
            )
            try:
                asr = float(item.get("asr") or item.get("callable_pass_rate") or 0.0)
            except (TypeError, ValueError):
                asr = 0.0
            series.append((str(label), max(0.0, min(asr, 1.0))))
    if not series:
        try:
            asr = float(data.get("callable_pass_rate") or 0.0)
        except (TypeError, ValueError):
            asr = 0.0
        series.append(("Results", max(0.0, min(asr, 1.0))))
    return series


def _render_overview(ctx: ReportContext) -> str:
    return ""


def _render_reasons(ctx: ReportContext) -> str:
    return ""


def _render_trial_table(ctx: ReportContext) -> str:
    if not ctx.trial_records:
        return "<p class=\"muted\">No trial rows found.</p>"

    header = (
        "<table class=\"trial-table\">"
        "<thead><tr><th>#</th><th>Prompt</th><th>Model output</th><th>Success</th><th>Reason</th></tr></thead><tbody>"
    )

    body_rows: List[str] = []
    for record in ctx.trial_records:
        payload = record.payload
        prompt = _extract_prompt(payload)
        output = _extract_output(payload)
        success_icon, success_label = _format_success(payload)
        reason = _extract_reason(payload)

        body_rows.append(
            "<tr>"
            f"<td>{record.index}</td>"
            f"<td>{_render_cell(prompt)}</td>"
            f"<td>{_render_cell(output)}</td>"
            f"<td class=\"success\">{success_icon}<span class=\"sr-only\">{html.escape(success_label)}</span></td>"
            f"<td>{_render_cell(reason)}</td>"
            "</tr>"
        )

    footer = "</tbody></table>"

    note_parts: List[str] = []
    if ctx.total_trials is not None and ctx.total_trials > ctx.trial_limit:
        note_parts.append(
            f"Showing first {len(ctx.trial_records)} of {ctx.total_trials} trials."
        )
    if ctx.rows_path:
        try:
            rel = ctx.rows_path.relative_to(ctx.run_dir)
            link_text = rel.as_posix()
        except ValueError:
            link_text = ctx.rows_path.name
        note_parts.append(
            f"See <code>{html.escape(link_text)}</code> for the full log."
        )
    note = "<p class=\"muted\">" + " &middot; ".join(note_parts) + "</p>" if note_parts else ""

    return header + "".join(body_rows) + footer + note


def _render_cell(text: str) -> str:
    if not text:
        return "<div class=\"io-cell muted\">—</div>"

    escaped_full = html.escape(text)
    if len(text) <= TRUNCATE_CHARS:
        return f"<div class=\"io-cell\"><pre>{escaped_full}</pre></div>"

    truncated = text[:TRUNCATE_CHARS]
    escaped_truncated = html.escape(truncated)
    return (
        "<div class=\"io-cell truncated\">"
        f"<pre class=\"io-short\">{escaped_truncated}…</pre>"
        f"<pre class=\"io-full\" hidden>{escaped_full}</pre>"
        "<button type=\"button\" class=\"io-toggle\">Show more</button>"
        "</div>"
    )


def _format_success(row: Mapping[str, Any]) -> Tuple[str, str]:
    raw = row.get("success")
    success = _coerce_bool(raw)
    if success is True:
        return "✓", "success"
    if success is False:
        return "✗", "failure"
    if isinstance(raw, str) and raw.strip():
        return html.escape(raw), raw
    if raw is not None:
        return html.escape(str(raw)), str(raw)
    return "—", "unknown"


def _coerce_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in {"pass", "success", "succeeded", "ok", "true", "1", "yes"}:
            return True
        if lower in {"fail", "failure", "false", "0", "no"}:
            return False
    return None


def _extract_prompt(row: Mapping[str, Any]) -> str:
    for path in (
        ("input", "attack_prompt"),
        ("input", "prompt"),
        ("attack_prompt",),
        ("prompt",),
    ):
        value = _dig(row, path)
        text = _stringify_text(value)
        if text:
            return text

    for path in (
        ("messages",),
        ("input", "messages"),
        ("request", "messages"),
        ("request", "input", "messages"),
    ):
        value = _dig(row, path)
        text = _join_user_messages(value)
        if text:
            return text

    value = row.get("input")
    text = _stringify_text(value)
    if text:
        return text

    return ""


def _extract_output(row: Mapping[str, Any]) -> str:
    for path in (
        ("output_text",),
        ("response", "text"),
        ("response", "output_text"),
        ("completion", "text"),
        ("output", "text"),
        ("response", "content"),
        ("completion", "choices"),
        ("output",),
        ("response",),
        ("completion",),
    ):
        value = _dig(row, path)
        text = _stringify_text(value)
        if text:
            return text
    return ""


def _extract_reason(row: Mapping[str, Any]) -> str:
    for path in (
        ("judge_reason",),
        ("reason",),
        ("why",),
        ("post_reason",),
        ("pre_reason",),
        ("callable_reason",),
        ("judge", "reason"),
        ("response", "reason"),
    ):
        value = _dig(row, path)
        text = _stringify_text(value)
        if text:
            return text
    return ""


def _join_user_messages(value: Any) -> str:
    if not isinstance(value, Iterable):
        return ""
    parts: List[str] = []
    for message in value:
        if not isinstance(message, Mapping):
            continue
        role = message.get("role")
        if role and str(role).lower() != "user":
            continue
        text = _stringify_text(message.get("content"))
        if not text:
            text = _stringify_text(message.get("text"))
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _stringify_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, Mapping):
        if "text" in value:
            return _stringify_text(value.get("text"))
        if "content" in value:
            return _stringify_text(value.get("content"))
        if "message" in value:
            return _stringify_text(value.get("message"))
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        parts = []
        for item in value:
            if isinstance(item, Mapping) and item.get("type") == "text":
                text = _stringify_text(item.get("text"))
            else:
                text = _stringify_text(item)
            if text:
                parts.append(text)
        if parts:
            return "\n".join(parts)
    return str(value)


def _render_artifacts(ctx: ReportContext) -> str:
    artifacts = []
    for name in ("summary.csv", "summary.svg", "run.json", "rows.jsonl", "summary_index.json"):
        path = ctx.run_dir / name
        if path.exists():
            artifacts.append(f"<li><a href=\"{name}\">{name}</a></li>")
    if artifacts:
        return "<ul class=\"artifact-list\">" + "".join(artifacts) + "</ul>"
    return "<p class=\"muted\">No artifacts found.</p>"


def _dig(mapping: Mapping[str, Any], path: Sequence[str]) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


_CSS = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;background:#f9fafb;color:#1f2933;}
h1{margin:0 0 12px;font-size:28px;font-weight:650;}
h2{margin:32px 0 12px;font-size:20px;font-weight:600;}
section{margin-bottom:32px;}
.page-header{margin-bottom:12px;}
.meta{color:#52606d;font-size:13px;display:flex;flex-wrap:wrap;gap:8px;}
.meta div{background:#e4e7eb;color:#364152;padding:4px 8px;border-radius:6px;}
.badge{display:inline-flex;align-items:center;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:600;background:#e4e7eb;color:#1f2933;}
.bar-row{display:flex;align-items:center;gap:12px;margin:8px 0;}
.bar-label{width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.bar-track{flex:1;height:16px;background:#e4e7eb;border-radius:8px;overflow:hidden;}
.bar-fill{height:100%;background:#5b8def;}
.bar-value{width:60px;text-align:right;font-variant-numeric:tabular-nums;}
.trial-table{width:100%;max-width:1100px;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 2px rgba(15,23,42,0.08);}
.trial-table th,.trial-table td{border:1px solid #e5e7eb;padding:8px 10px;font-size:14px;vertical-align:top;}
.trial-table th{background:#f3f4f6;font-weight:600;}
.io-cell{max-height:11em;overflow:hidden;white-space:pre-wrap;word-break:break-word;}
.io-cell pre{margin:0;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:13px;line-height:1.45;}
.io-cell.truncated{position:relative;padding-bottom:32px;}
.io-cell.truncated .io-toggle{position:absolute;bottom:6px;left:0;font-size:12px;background:none;border:none;color:#2563eb;cursor:pointer;padding:0;}
.io-cell.truncated .io-full{background:#fff;}
.io-cell.muted{color:#94a3b8;}
.success{font-size:18px;text-align:center;}
.muted{color:#6b7280;font-size:14px;}
.artifact-list{list-style:none;padding:0;margin:0;}
.artifact-list li{margin:6px 0;font-size:14px;}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;}
@media (prefers-color-scheme:dark){
  body{background:#111827;color:#f3f4f6;}
  .meta div{background:rgba(148,163,184,0.2);color:#e2e8f0;}
  .badge{background:rgba(148,163,184,0.2);color:#f9fafb;}
  .trial-table{background:#1f2937;box-shadow:0 1px 2px rgba(0,0,0,0.35);}
  .trial-table th{background:#27303f;}
  .trial-table td,.trial-table th{border-color:#374151;}
  .io-cell.truncated .io-full{background:#1f2937;}
  .bar-track{background:#334155;}
}
"""


_SCRIPT = """
document.addEventListener('click', (event) => {
  const button = event.target;
  if (!button.classList.contains('io-toggle')) {
    return;
  }
  const cell = button.closest('.io-cell');
  if (!cell) {
    return;
  }
  const shortEl = cell.querySelector('.io-short');
  const fullEl = cell.querySelector('.io-full');
  const expanded = fullEl && !fullEl.hasAttribute('hidden');
  if (expanded) {
    if (fullEl) {
      fullEl.setAttribute('hidden', '');
    }
    if (shortEl) {
      shortEl.removeAttribute('hidden');
    }
    button.textContent = 'Show more';
  } else {
    if (fullEl) {
      fullEl.removeAttribute('hidden');
    }
    if (shortEl) {
      shortEl.setAttribute('hidden', '');
    }
    button.textContent = 'Show less';
  }
});
"""


def render_html(run_dir: Path, ctx_data: Mapping[str, Any], mode: str = "context") -> str:
    """Compatibility wrapper for older call sites.

    Parameters
    ----------
    run_dir:
        Root directory containing the run artifacts.
    ctx_data:
        Either a mapping produced by :class:`ReportContext` or a dictionary
        with a ``context`` key. This wrapper exists to preserve older tests
        that import :func:`render_html` directly.
    mode:
        Ignored; retained for compatibility only.
    """

    if isinstance(ctx_data, ReportContext):
        context = ctx_data
    elif "context" in ctx_data and isinstance(ctx_data["context"], ReportContext):
        context = ctx_data["context"]
    else:
        raise TypeError("render_html wrapper expects a ReportContext payload")
    return render_report(context)


__all__ = ["ReportContext", "TrialRecord", "render_report", "render_html"]


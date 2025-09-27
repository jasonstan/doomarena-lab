from __future__ import annotations

import argparse
import json
import os
import sys
from html import escape
from pathlib import Path
from string import Template
from typing import Any, Dict, Iterator, Mapping, Optional, Tuple

try:
    from tools.aggregate import SummarySnapshot, stream_summary
except ModuleNotFoundError:  # pragma: no cover - script invoked from tools/
    from aggregate import SummarySnapshot, stream_summary  # type: ignore

try:
    from tools.svg_chart import render_compact_asr_chart
except ModuleNotFoundError:  # pragma: no cover - script invoked from tools/
    from svg_chart import render_compact_asr_chart  # type: ignore

try:
    from tools.report.html_utils import esc
except Exception:  # fallback for older runners
    import html

    def esc(s: object) -> str:
        if s is None:
            return ""
        return html.escape(str(s), quote=True)

try:
    from tools.report_utils import get_prompt, get_response
except ModuleNotFoundError:  # pragma: no cover - script invoked from tools/
    from report_utils import get_prompt, get_response  # type: ignore


PROMPT_KEYS = [
    ("input_text", None),
    ("input_case", "prompt"),
    ("input", "prompt"),
    ("attack_prompt", None),
    ("prompt", None),
]


RESPONSE_KEYS = [
    ("output_text", None),
    ("model_response", None),
    ("response", "text"),
    ("response", None),
    ("output", None),
    ("model_output", None),
]


EMPTY_SENTINEL = "[EMPTY]"


def pick(row: Mapping[str, Any], keys: list[tuple[str, Optional[str]]]) -> str:
    for outer, inner in keys:
        value = row.get(outer)
        if inner is None:
            if value:
                return str(value)
            continue
        if isinstance(value, Mapping):
            candidate = value.get(inner)
            if candidate:
                return str(candidate)
    return "—"


def expander(block_id: str, text: Optional[str], limit: int = 240) -> str:
    full_text = text or ""
    preview = full_text[:limit] + ("…" if len(full_text) > limit else "")
    safe_id = escape(block_id, quote=True)
    preview_html = escape(preview, quote=False)
    full_html = escape(full_text, quote=False)
    return (
        '<div class="expander">'
        f'<div class="preview">{preview_html}</div>'
        f'<div id="{safe_id}" class="fulltext" style="display:none;">{full_html}</div>'
        f'<button class="toggle" data-expands="{safe_id}">Expand</button>'
        "</div>"
    )


def _read_jsonl_lines(p: Path) -> Iterator[Dict[str, Any]]:
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def _format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _render_summary_overview(snapshot: SummarySnapshot) -> str:
    totals = snapshot.totals
    pieces = [
        "<ul class=\"summary-overview\">",
        f"<li><strong>Total trials:</strong> {totals.total}</li>",
        f"<li><strong>Callable:</strong> {totals.callable_true} ({_format_percent(totals.callable_rate())})</li>",
        f"<li><strong>Success:</strong> {totals.success_true} ({_format_percent(totals.pass_rate())})</li>",
    ]
    if snapshot.malformed_rows:
        pieces.append(
            f"<li><strong>Malformed rows skipped:</strong> {snapshot.malformed_rows}</li>"
        )
    pieces.append("</ul>")
    return "".join(pieces)


def _render_summary_table(snapshot: SummarySnapshot) -> str:
    totals = snapshot.totals
    rows: list[str] = [
        "<table class=\"summary-table\">",
        "<thead><tr><th>Slice</th><th>Persona</th><th>Trials</th><th>Callable</th><th>Success</th><th>Callable%</th><th>Pass%</th></tr></thead>",
        "<tbody>",
    ]
    rows.append(
        "<tr class=\"summary-total\">"
        "<td><strong>Total</strong></td>"
        "<td>—</td>"
        f"<td>{totals.total}</td>"
        f"<td>{totals.callable_true}</td>"
        f"<td>{totals.success_true}</td>"
        f"<td>{_format_percent(totals.callable_rate())}</td>"
        f"<td>{_format_percent(totals.pass_rate())}</td>"
        "</tr>"
    )
    for entry in snapshot.slice_persona:
        counts = entry.counts
        rows.append(
            "<tr>"
            f"<td>{esc(entry.slice_id)}</td>"
            f"<td>{esc(entry.persona)}</td>"
            f"<td>{counts.total}</td>"
            f"<td>{counts.callable_true}</td>"
            f"<td>{counts.success_true}</td>"
            f"<td>{_format_percent(counts.callable_rate())}</td>"
            f"<td>{_format_percent(counts.pass_rate())}</td>"
            "</tr>"
        )
    rows.append("</tbody></table>")
    return "".join(rows)


def _read_model_seed(run_dir: Path) -> Tuple[Optional[str], Optional[str]]:
    run_json = run_dir / "run.json"
    model = seed = None
    if run_json.exists():
        try:
            meta = json.loads(run_json.read_text(encoding="utf-8"))
            model = (
                meta.get("config", {}).get("provider", {}).get("model")
                or meta.get("provider_model")
                or meta.get("model")
            )
            seed = str(
                meta.get("config", {}).get("seed")
                or meta.get("seed")
                or ""
            ) or None
        except Exception:
            pass
    return model, seed


def _find_rows_file(run_dir: Path) -> Optional[Path]:
    direct = run_dir / "rows.jsonl"
    if direct.exists():
        return direct
    for candidate in run_dir.rglob("rows.jsonl"):
        if candidate.is_file():
            return candidate
    return None


def _resolve_table_cap() -> int:
    for name in ("REPORT_MAX_TRIAL_ROWS", "TRIAL_TABLE_LIMIT"):
        candidate = os.getenv(name)
        if candidate is None:
            continue
        try:
            value = int(candidate)
        except ValueError:
            continue
        if value > 0:
            return value
    return 1000


MAX_TABLE_ROWS = _resolve_table_cap()
DEFAULT_TRIAL_LIMIT = MAX_TABLE_ROWS


def _load_trial_template() -> Template:
    template_path = Path(__file__).resolve().parent / "templates" / "report.html.j2"
    try:
        text = template_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Fallback template keeps the page valid even if the asset is missing.
        text = (
            "<section id=\"trial-io\">"
            "<h2>Trial I/O</h2>"
            "<p class=\"muted\">$status_line</p>"
            "$warning_banner"
            "<table class=\"io-table\">"
            "<thead><tr><th>trial_id</th><th>attack_id</th><th>success</th><th>input</th><th>output</th></tr></thead>"
            "<tbody>$table_rows</tbody>"
            "</table>"
            "<p class=\"muted\">Raw artifacts: <a href=\"$rel_root/rows.jsonl\">rows.jsonl</a> · "
            "<a href=\"$rel_root/summary.csv\">summary.csv</a></p>"
            "</section>"
        )
    return Template(text)


def _escape_for_template(value: str) -> str:
    if not value:
        return value
    return value.replace("$", "$$")


def _format_success(value: Any) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return "✅"
        if normalized in {"false", "0", "no"}:
            return "❌"
    if value is True:
        return "✅"
    if value is False:
        return "❌"
    return "—"


def _resolve_trial_id(row: Mapping[str, Any], fallback_index: int) -> str:
    for key in ("trial_id", "id", "trial", "trial_index"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    input_case = row.get("input_case")
    if isinstance(input_case, Mapping):
        for key in ("trial_id", "id", "trial", "trial_index", "prompt_id"):
            value = input_case.get(key)
            if value not in (None, ""):
                return str(value)
    return str(fallback_index)


def _resolve_attack_id(row: Mapping[str, Any]) -> str:
    for key in ("attack_id", "attack", "attack_index", "attack_idx"):
        value = row.get(key)
        if value not in (None, "", "—"):
            return str(value)
    input_case = row.get("input_case")
    if isinstance(input_case, Mapping):
        for key in ("attack_id", "attack", "id"):
            value = input_case.get(key)
            if value not in (None, "", "—"):
                return str(value)
    return "—"


def _normalize_for_expander(value: Optional[str]) -> str:
    if value is None:
        return ""
    return value


def _is_preview_empty(value: Optional[str]) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    return stripped == "" or stripped == "—" or stripped == EMPTY_SENTINEL


def _build_trial_row(row: Mapping[str, Any], index: int) -> Dict[str, str]:
    trial_id_raw = _resolve_trial_id(row, index)
    attack_id_raw = _resolve_attack_id(row)
    prompt_txt = pick(row, PROMPT_KEYS)
    if prompt_txt == "—":
        legacy_prompt = get_prompt(row)
        if legacy_prompt:
            prompt_txt = legacy_prompt

    response_txt = pick(row, RESPONSE_KEYS)
    if response_txt == "—":
        legacy_response = get_response(row)
        if legacy_response:
            response_txt = legacy_response

    prompt_html = expander(f"p-{trial_id_raw}", _normalize_for_expander(prompt_txt))
    response_html = expander(f"r-{trial_id_raw}", _normalize_for_expander(response_txt))

    success_value = row.get("success")
    if success_value in (None, "", "—"):
        success_value = row.get("judge_success")

    return {
        "trial_id": esc(trial_id_raw),
        "attack_id": esc(attack_id_raw),
        "success": _format_success(success_value),
        "prompt_html": prompt_html,
        "response_html": response_html,
        "prompt_raw": prompt_txt,
        "response_raw": response_txt,
    }


def _collect_trial_rows(
    rows_path: Path, max_rows: int
) -> Tuple[list[Dict[str, str]], int, Dict[str, int]]:
    table_rows: list[Dict[str, str]] = []
    total_callable = 0
    missing_inputs = 0
    missing_outputs = 0

    for idx, row in enumerate(_read_jsonl_lines(rows_path)):
        if row.get("callable") is True:
            total_callable += 1
            if len(table_rows) >= max_rows:
                continue
            built = _build_trial_row(row, idx)
            if _is_preview_empty(built.get("prompt_raw")):
                missing_inputs += 1
            if _is_preview_empty(built.get("response_raw")):
                missing_outputs += 1
            table_rows.append(built)

    return table_rows, total_callable, {"inputs": missing_inputs, "outputs": missing_outputs}


def _render_trial_table_rows(rows: list[Dict[str, str]]) -> str:
    rendered: list[str] = []
    for row in rows:
        rendered.append(
            "<tr>"
            f"<td>{row['trial_id']}</td>"
            f"<td>{row['attack_id']}</td>"
            f"<td>{row['success']}</td>"
            f"<td>{row['prompt_html']}</td>"
            f"<td>{row['response_html']}</td>"
            "</tr>"
        )
    return "\n".join(rendered)


def _load_run_meta(run_dir: Path) -> Dict[str, Any]:
    run_json = run_dir / "run.json"
    if not run_json.exists():
        return {}
    try:
        return json.loads(run_json.read_text(encoding="utf-8"))
    except Exception:
        return {}


def render_trial_io_section(run_dir: Path, *, trial_limit: int) -> str:
    template = _load_trial_template()
    rows_path = _find_rows_file(run_dir)
    rel_root = "."

    run_meta = _load_run_meta(run_dir)
    total_trials_meta: Any = run_meta.get("trials")
    if total_trials_meta is None:
        total_trials_meta = run_meta.get("total_trials")
    try:
        total_trials = int(total_trials_meta)
    except (TypeError, ValueError):
        total_trials = "—"

    cap = trial_limit if trial_limit > 0 else MAX_TABLE_ROWS
    cap = min(cap, MAX_TABLE_ROWS)

    rendered_rows: list[Dict[str, str]] = []
    warning_banner = ""
    if not rows_path:
        status_line = "No per-trial rows found (rows.jsonl missing)."
        rows_html = '<tr><td colspan="5" class="muted">No rows recorded.</td></tr>'
        table_rows: list[Dict[str, str]] = []
        shown_n = 0
        total_callable = 0
        trials_display = "—"
    else:
        table_rows, total_callable, missing_counts = _collect_trial_rows(rows_path, cap)
        shown_n = len(table_rows)
        rendered_rows = [
            {
                "trial_id": row["trial_id"],
                "attack_id": row["attack_id"],
                "success": row["success"],
                "prompt_html": row["prompt_html"],
                "response_html": row["response_html"],
            }
            for row in table_rows
        ]
        rows_html = _render_trial_table_rows(rendered_rows)
        trials_display = str(total_trials) if total_trials != "—" else "—"

        total_previews = shown_n * 2
        if total_callable == 0:
            status_line = "No callable trials—check pre/post gates or budgets."
            if not rows_html:
                rows_html = '<tr><td colspan="5" class="muted">No callable trials recorded.</td></tr>'
        else:
            status_line = (
                "showing "
                f"{shown_n} of {total_callable} callable trials; round-robin across {trials_display} trials"
            )
            if not rows_html:
                rows_html = (
                    '<tr><td colspan="5" class="muted">'
                    "No callable trials available within the current trial limit."
                    "</td></tr>"
                )
            if total_previews:
                missing_previews = missing_counts["inputs"] + missing_counts["outputs"]
                missing_ratio = missing_previews / total_previews
                if missing_ratio >= 0.5:
                    warning_banner = (
                        "<div class=\"warning\">⚠️ WARNING: Most callable trial inputs/outputs appear empty. "
                        "Ensure literal prompt/response persistence is configured.</div>"
                    )

    context = {
        "trial_table": rendered_rows if rows_path else [],
        "shown_n": shown_n,
        "total_callable": total_callable,
        "total_trials": trials_display,
        "warning_banner": warning_banner,
    }

    return template.substitute(
        status_line=_escape_for_template(status_line),
        table_rows=_escape_for_template(rows_html),
        warning_banner=_escape_for_template(warning_banner),
        rel_root=rel_root,
        shown_n=shown_n,
        total_callable=total_callable,
        total_trials=trials_display,
    )


def _append_badges(run_dir: Path) -> str:
    model, seed = _read_model_seed(run_dir)
    bits = []
    if model:
        bits.append(
            "<span style='padding:2px 8px;border:1px solid #ddd;border-radius:12px;'>Model: "
            f"<code>{esc(model)}</code></span>"
        )
    if seed:
        bits.append(
            "<span style='padding:2px 8px;border:1px solid #ddd;border-radius:12px;margin-left:8px;'>Seed: "
            f"<code>{esc(seed)}</code></span>"
        )
    if not bits:
        return ""
    return "<p>" + " ".join(bits) + "</p>"


def _read_file_safe(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def build_full_html(run_dir: Path, trial_limit: int) -> str:
    summary_svg = run_dir / "summary.svg"
    rows_path = _find_rows_file(run_dir)

    snapshot: Optional[SummarySnapshot] = None
    if rows_path and rows_path.exists():
        try:
            snapshot = stream_summary(rows_path)
        except Exception:
            snapshot = None

    if snapshot and snapshot.has_trials():
        overview_html = _render_summary_overview(snapshot)
        chart_html = render_compact_asr_chart(snapshot.chart_bars())
        table_html = _render_summary_table(snapshot)
    else:
        if snapshot and snapshot.malformed_rows:
            overview_html = (
                f"<p class=\"muted\">No trials recorded; skipped {snapshot.malformed_rows} malformed rows.</p>"
            )
        else:
            overview_html = "<p class=\"muted\">No trials recorded.</p>"
        if summary_svg.exists():
            chart_html = _read_file_safe(summary_svg)
        else:
            chart_html = render_compact_asr_chart([])
        table_html = "<p class=\"muted\">No summary data available.</p>"

    parts: list[str] = []
    parts.append("<!doctype html><meta charset='utf-8'>")
    parts.append("<title>DoomArena-Lab Report</title>")
    parts.append(
        "<style>body{font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,Helvetica,Arial}"
        "table td,table th{font-size:12.5px}</style>"
    )
    parts.append("<h1>DoomArena-Lab Report</h1>")
    parts.append(_append_badges(run_dir))

    parts.append("<section><h2>Overview</h2>")
    parts.append(overview_html)
    parts.append("</section>")

    parts.append("<section><h2>Attack result (ASR)</h2>")
    parts.append(chart_html)
    parts.append("</section>")

    parts.append("<section><h2>Summary table</h2>")
    parts.append(table_html)
    parts.append("</section>")

    parts.append(render_trial_io_section(run_dir, trial_limit=trial_limit))

    parts.append("<section><h2>Artifacts</h2><ul>")
    for name in ("summary.csv", "summary.svg", "rows.jsonl", "run.json"):
        p = run_dir / name
        if p.exists():
            parts.append(f"<li><a href='{esc(str(name))}'>{esc(name)}</a></li>")
    parts.append("</ul></section>")

    return "\n".join(parts)


def resolve_run_dir(requested: Path) -> Path:
    path = requested.expanduser()
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path

    if resolved.exists():
        return resolved

    pointer = path.parent / f"{path.name}.path"
    if pointer.exists():
        try:
            target_text = pointer.read_text(encoding="utf-8").strip()
        except Exception:
            target_text = ""
        if target_text:
            target = Path(target_text)
            if not target.is_absolute():
                target = (pointer.parent / target_text)
            try:
                target_resolved = target.resolve()
            except Exception:
                target_resolved = target
            if target_resolved.exists():
                return target_resolved
            return target_resolved

    return resolved


def main(run_dir_arg: str, *, trial_limit: int) -> int:
    requested = Path(run_dir_arg)
    run_dir = resolve_run_dir(requested)
    run_dir.mkdir(parents=True, exist_ok=True)
    index = run_dir / "index.html"
    try:
        html = build_full_html(run_dir, trial_limit)
        index.write_text(html, encoding="utf-8")
        return 0
    except Exception as e:
        index.write_text(f"<h1>Report (degraded)</h1><pre>{esc(e)}</pre>", encoding="utf-8")
        return 1


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Render DoomArena reports")
    env_limit = os.environ.get("TRIAL_TABLE_LIMIT") or os.environ.get("REPORT_MAX_TRIAL_ROWS")
    default_limit = DEFAULT_TRIAL_LIMIT
    if env_limit is not None:
        try:
            parsed = int(env_limit)
        except ValueError:
            parsed = DEFAULT_TRIAL_LIMIT
        if parsed > 0:
            default_limit = min(parsed, MAX_TABLE_ROWS)
    parser.add_argument("run_dir", help="Run directory containing summary artifacts")
    parser.add_argument(
        "--trial-limit",
        type=int,
        default=default_limit,
        help=(
            "Maximum number of callable trials to include in the I/O table "
            f"(default: {default_limit})"
        ),
    )
    args = parser.parse_args(argv[1:])
    limit = args.trial_limit if args.trial_limit and args.trial_limit > 0 else DEFAULT_TRIAL_LIMIT
    limit = min(limit, MAX_TABLE_ROWS)
    return main(args.run_dir, trial_limit=limit)


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))

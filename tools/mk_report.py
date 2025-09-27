from __future__ import annotations

import argparse
import json
import os
import sys
from collections import OrderedDict, deque
from collections.abc import Iterable, Sequence
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
    from tools.report_utils import expandable_block, safe_get, truncate_for_preview
except ModuleNotFoundError:  # pragma: no cover - script invoked from tools/
    from report_utils import expandable_block, safe_get, truncate_for_preview


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


def _join_user_messages(messages: Any) -> Optional[str]:
    if not isinstance(messages, Iterable) or isinstance(messages, (str, bytes, bytearray)):
        return None
    parts = []
    for message in messages:
        if not isinstance(message, Mapping):
            continue
        role = message.get("role")
        if role and str(role).lower() not in {"user", "system"}:
            continue
        text = _stringify_text(message.get("content"))
        if not text:
            text = _stringify_text(message.get("text"))
        if text.strip():
            parts.append(text)
    if parts:
        return "\n\n".join(parts)
    return None


def _stringify_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, Mapping):
        for key in ("text", "content", "message"):
            if key in value:
                return _stringify_text(value.get(key))
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
        return ""
    return str(value)


def _dig(mapping: Mapping[str, Any], path: Sequence[str]) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _openai_like(raw: Any) -> Optional[str]:
    try:
        return raw["choices"][0]["message"]["content"]
    except Exception:
        try:
            return raw["choices"][0]["text"]
        except Exception:
            return None


def _extract_prompt(row: Dict[str, Any]) -> Optional[str]:
    candidate_paths = (
        ("input_text",),
        ("input", "input_text"),
        ("input", "attack_prompt"),
        ("input", "prompt"),
        ("input_case", "attack_prompt"),
        ("input_case", "prompt"),
        ("request", "input", "attack_prompt"),
        ("request", "input", "prompt"),
        ("request", "attack_prompt"),
        ("request", "prompt"),
        ("attack_prompt",),
        ("prompt",),
        ("input",),
    )
    for path in candidate_paths:
        value = _dig(row, path)
        text = _stringify_text(value)
        if text.strip():
            return text

    for path in (
        ("messages",),
        ("input", "messages"),
        ("input_case", "messages"),
        ("request", "messages"),
        ("request", "input", "messages"),
    ):
        text = _join_user_messages(_dig(row, path))
        if text:
            return text

    return None


def _extract_response(row: Dict[str, Any]) -> Optional[str]:
    candidate_paths = (
        ("output_text",),
        ("output", "text"),
        ("output", "content"),
        ("output", "message", "content"),
        ("output", "choices"),
        ("response", "text"),
        ("response", "output_text"),
        ("response", "content"),
        ("response", "message", "content"),
        ("response", "choices"),
        ("completion", "text"),
        ("completion", "choices"),
        ("completion",),
        ("output",),
        ("response",),
        ("model_output",),
    )
    for path in candidate_paths:
        value = _dig(row, path)
        text = _stringify_text(value)
        if text.strip():
            return text

    raw = row.get("raw_output")
    txt = _openai_like(raw)
    if isinstance(txt, str) and txt.strip():
        return txt
    return None


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


DEFAULT_TRIAL_LIMIT = 20


def _load_trial_template() -> Template:
    template_path = Path(__file__).resolve().parent / "templates" / "report.html.j2"
    try:
        text = template_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Fallback template keeps the page valid even if the asset is missing.
        text = (
            "<section id=\"trial-io\">"
            "<h2>Trial I/O</h2>"
            "$banner\n"
            "$table_html\n"
            "</section>"
        )
    return Template(text)


def _escape_for_template(value: str) -> str:
    if not value:
        return value
    return value.replace("$", "$$")


def _format_success(value: Any) -> str:
    if value is True:
        return "✅"
    if value is False:
        return "❌"
    return "—"


def _format_callable(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "—"


def _format_gate(value: Any) -> str:
    if isinstance(value, Mapping):
        decision = safe_get(value, "decision", "") or safe_get(value, "status", "")
        reason = safe_get(value, "reason", "")
        if reason == "—":
            reason = safe_get(value, "reason_code", "")
        if reason == "—":
            reason = safe_get(value, "rule_id", "")
        pieces = [str(part) for part in (decision, reason) if part not in (None, "", "—")]
        if pieces:
            return " / ".join(pieces)
    elif value not in (None, ""):
        return str(value)
    return "—"


def _trial_key(row: Mapping[str, Any], fallback: int) -> Tuple[str, bool]:
    candidates = (
        "trial_id",
        "trial",
        "trial_index",
        "case_index",
    )
    for key in candidates:
        value = row.get(key)
        if value not in (None, ""):
            return str(value), True
    input_case = row.get("input_case")
    if isinstance(input_case, Mapping):
        for key in ("trial_id", "trial_index", "id", "prompt_id"):
            value = input_case.get(key)
            if value not in (None, ""):
                return str(value), True
    return f"row-{fallback}", False


def _stream_callable_trials(rows_path: Path, limit: int) -> Tuple[list[Mapping[str, Any]], int, int]:
    buckets: "OrderedDict[str, deque[Mapping[str, Any]]]" = OrderedDict()
    key_order: list[str] = []
    selected: list[Mapping[str, Any]] = []
    total_callable = 0
    trial_keys_seen: set[str] = set()
    cycle_index = 0

    for idx, row in enumerate(_read_jsonl_lines(rows_path)):
        trial_key, is_concrete = _trial_key(row, idx)
        if is_concrete:
            trial_keys_seen.add(trial_key)

        if row.get("callable") is True:
            total_callable += 1
            if len(selected) >= limit:
                continue

            if trial_key not in buckets:
                buckets[trial_key] = deque()
                key_order.append(trial_key)

            buckets[trial_key].append(row)
            cycle_index = _round_robin_drain(buckets, key_order, selected, limit, cycle_index)

            if len(selected) >= limit:
                buckets.clear()
                key_order.clear()

    return selected, total_callable, len(trial_keys_seen)


def _round_robin_drain(
    buckets: "OrderedDict[str, deque[Mapping[str, Any]]]",
    key_order: list[str],
    selected: list[Mapping[str, Any]],
    limit: int,
    cycle_index: int,
) -> int:
    if not key_order:
        return cycle_index

    made_progress = True
    total_keys = len(key_order)
    while len(selected) < limit and made_progress:
        made_progress = False
        for _ in range(total_keys):
            if not key_order:
                return cycle_index
            key = key_order[cycle_index % len(key_order)]
            cycle_index += 1
            queue = buckets.get(key)
            if queue:
                selected.append(queue.popleft())
                made_progress = True
                if len(selected) >= limit:
                    break
        if not made_progress:
            break
    return cycle_index


def _resolve_trial_id(row: Mapping[str, Any], fallback_index: int) -> str:
    for key in ("trial_id", "trial", "trial_index", "id"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    input_case = row.get("input_case")
    if isinstance(input_case, Mapping):
        for key in ("trial_id", "trial_index", "id"):
            value = input_case.get(key)
            if value not in (None, ""):
                return str(value)
    return str(fallback_index + 1)


def _render_trial_rows(rows: list[Mapping[str, Any]]) -> Tuple[str, int]:
    rendered_rows: list[str] = []
    for idx, row in enumerate(rows):
        trial_id = esc(_resolve_trial_id(row, idx))
        callable_text = esc(_format_callable(row.get("callable")))
        pre_gate = esc(_format_gate(row.get("pre_gate")))
        post_gate = esc(_format_gate(row.get("post_gate")))
        success = _format_success(row.get("success"))

        prompt_full = _extract_prompt(row) or ""
        response_full = _extract_response(row) or ""
        prompt_preview = truncate_for_preview(prompt_full)
        response_preview = truncate_for_preview(response_full)

        prompt_html = expandable_block(
            f"prompt-{idx}",
            prompt_preview,
            prompt_full,
        )
        response_html = expandable_block(
            f"response-{idx}",
            response_preview,
            response_full,
        )

        rendered_rows.append(
            "<tr>"
            f"<td>{trial_id}</td>"
            f"<td>{callable_text}</td>"
            f"<td>{pre_gate}</td>"
            f"<td>{post_gate}</td>"
            f"<td>{success}</td>"
            f"<td>{prompt_html}</td>"
            f"<td>{response_html}</td>"
            "</tr>"
        )
    return "\n".join(rendered_rows), len(rows)


def render_trial_io_section(run_dir: Path, *, trial_limit: int) -> str:
    template = _load_trial_template()
    rows_path = _find_rows_file(run_dir)
    rel_root = "."

    if not rows_path:
        return template.substitute(
            banner=_escape_for_template(
                "<p class=\"muted\">No per-trial rows found (rows.jsonl missing).</p>"
            ),
            table_html="",
            rel_root=rel_root,
            shown_n=0,
            total_callable=0,
            total_trials=0,
        )

    sampled_rows, total_callable, total_trials = _stream_callable_trials(rows_path, trial_limit)
    rows_html, shown_n = _render_trial_rows(sampled_rows)
    display_trials = total_trials or max(total_callable, shown_n, 0)

    if total_callable == 0:
        banner = "<p class=\"muted\">No callable trials—check pre/post gates or budgets.</p>"
        table_html = ""
    else:
        banner = (
            "<p class=\"muted\">showing "
            f"{shown_n} of {total_callable} callable trials; round-robin across {display_trials} trials."  # noqa: E501
            "</p>"
        )
        table_html = (
            "<table class=\"io-table\">"
            "<thead>"
            "<tr>"
            "<th>trial_id</th><th>callable</th><th>pre_gate</th>"
            "<th>post_gate</th><th>success</th><th>prompt</th><th>response</th>"
            "</tr>"
            "</thead>"
            "<tbody>"
            f"{rows_html}"
            "</tbody>"
            "</table>"
        )

    return template.substitute(
        banner=_escape_for_template(banner),
        table_html=_escape_for_template(table_html),
        rel_root=rel_root,
        shown_n=shown_n,
        total_callable=total_callable,
        total_trials=display_trials,
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
    env_limit = os.environ.get("TRIAL_TABLE_LIMIT")
    try:
        default_limit = int(env_limit) if env_limit is not None else DEFAULT_TRIAL_LIMIT
    except ValueError:
        default_limit = DEFAULT_TRIAL_LIMIT
    parser.add_argument("run_dir", help="Run directory containing summary artifacts")
    parser.add_argument(
        "--trial-limit",
        type=int,
        default=default_limit,
        help=f"Number of callable trials to sample for the I/O table (default: {default_limit})",
    )
    args = parser.parse_args(argv[1:])
    limit = args.trial_limit if args.trial_limit > 0 else DEFAULT_TRIAL_LIMIT
    return main(args.run_dir, trial_limit=limit)


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))

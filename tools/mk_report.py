import ast
import csv
import html
import json
import sys
from itertools import chain
from pathlib import Path
from string import Template
from typing import Iterable, Iterator, Mapping


TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "reports" / "templates" / "index.html"
REPORT_JSON_NAME = "run_report.json"


def read_rows(csv_path: Path) -> tuple[list[str], Iterable[dict[str, str]]]:
    if not csv_path.exists():
        return [], iter(())

    handle = csv_path.open(newline="")
    reader = csv.DictReader(handle)
    headers = [(head or "").strip() for head in reader.fieldnames or []]

    def _iter_rows() -> Iterator[dict[str, str]]:
        try:
            for record in reader:
                yield {
                    (key or "").strip(): (value or "") for key, value in record.items()
                }
        finally:
            handle.close()

    return headers, _iter_rows()


def load_run_meta(run_dir: Path) -> dict[str, object]:
    payload: dict[str, object] = {}
    run_json = run_dir / "run.json"
    if not run_json.exists():
        return payload
    try:
        data = json.loads(run_json.read_text(encoding="utf-8"))
    except Exception:
        return payload
    if isinstance(data, dict):
        payload = data
    return payload


def _load_chart_css() -> str:
    css_path = Path(__file__).resolve().parent / "report" / "assets" / "chart.css"
    try:
        text = css_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    stripped = text.strip()
    if not stripped:
        return ""
    return stripped + "\n"


def _normalise_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _parse_config_blob(blob: object) -> dict[str, object]:
    if blob is None:
        return {}
    if isinstance(blob, dict):
        return blob
    text = _normalise_text(blob)
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(text)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}


def _first_nonempty(values: list[str]) -> str:
    for value in values:
        if value:
            return value
    return ""


def _collect_seed_badges(meta: Mapping[str, object], summary_snapshot: Mapping[str, str]) -> str:
    seeds: list[str] = []
    seen: set[str] = set()

    def _add(value: object) -> None:
        if value is None:
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                _add(item)
            return
        text = _normalise_text(value)
        if not text:
            return
        # split comma/semicolon separated strings
        for token in [chunk.strip() for chunk in text.replace(";", ",").split(",")]:
            if not token:
                continue
            if token in seen:
                continue
            seen.add(token)
            seeds.append(token)

    _add(meta.get("seed"))
    _add(meta.get("seeds"))
    config_blob = _parse_config_blob(summary_snapshot.get("config")) if summary_snapshot else {}
    if config_blob:
        _add(config_blob.get("seed"))
        _add(config_blob.get("seeds"))
    if summary_snapshot:
        _add(summary_snapshot.get("seed"))
        _add(summary_snapshot.get("seeds"))
    if not seeds:
        return "unknown"
    return ", ".join(seeds)


def _collect_model_badge(meta: Mapping[str, object], summary_snapshot: Mapping[str, str]) -> str:
    candidates: list[str] = []

    for key in ("model", "model_name", "llm", "llm_model"):
        value = meta.get(key)
        text = _normalise_text(value)
        if text:
            candidates.append(text)
    real_meta = meta.get("real")
    if isinstance(real_meta, Mapping):
        text = _normalise_text(real_meta.get("model"))
        if text:
            candidates.append(text)
    config_blob = _parse_config_blob(summary_snapshot.get("config")) if summary_snapshot else {}
    if config_blob:
        text = _normalise_text(config_blob.get("model"))
        if text:
            candidates.append(text)
    model_from_rows = _normalise_text(summary_snapshot.get("model")) if summary_snapshot else ""
    if model_from_rows:
        candidates.append(model_from_rows)
    choice = _first_nonempty(candidates)
    return choice or "unknown"


def _read_summary_snapshot(run_dir: Path) -> dict[str, str]:
    csv_path = run_dir / "summary.csv"
    if not csv_path.exists():
        return {}
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            try:
                first_row = next(reader)
            except StopIteration:
                return {}
            return {key: value for key, value in first_row.items() if key}
    except OSError:
        return {}


def _resolve_rows_path(run_dir: Path, report: Mapping[str, object]) -> tuple[Path | None, str]:
    direct = run_dir / "rows.jsonl"
    if direct.exists():
        return direct, "rows.jsonl"
    rows_paths = report.get("rows_paths") if isinstance(report, Mapping) else None
    if isinstance(rows_paths, list):
        for rel in rows_paths:
            rel_text = _normalise_text(rel)
            if not rel_text:
                continue
            candidate = run_dir / rel_text
            if candidate.exists():
                return candidate, rel_text
    return None, "rows.jsonl"


def _stringify_field(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def _truncate_text(value: str, limit: int = 160) -> str:
    if len(value) <= limit:
        return value
    if limit <= 1:
        return "…"
    return value[: limit - 1] + "…"


def _format_success(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = _normalise_text(value).lower()
    if text in {"true", "1", "yes", "y"}:
        return "yes"
    if text in {"false", "0", "no", "n"}:
        return "no"
    return text or "–"


def _extract_from_keys(payload: Mapping[str, object], keys: Iterable[str]) -> str:
    for key in keys:
        if key not in payload:
            continue
        text = _stringify_field(payload.get(key))
        if text:
            return text
    return ""


def _summarise_chart_rows(run_dir: Path) -> list[dict[str, object]]:
    csv_path = run_dir / "summary.csv"
    if not csv_path.exists():
        return []
    aggregates: dict[str, dict[str, object]] = {}
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            order_index = 0
            for row in reader:
                slice_id = _normalise_text(row.get("exp_id") or row.get("exp"))
                if not slice_id:
                    continue
                bucket = aggregates.get(slice_id)
                if bucket is None:
                    bucket = {
                        "id": slice_id,
                        "trials": 0,
                        "successes": 0.0,
                        "asr_values": [],
                        "order": order_index,
                    }
                    order_index += 1
                    aggregates[slice_id] = bucket
                trials_value = _parse_optional_int(row.get("trials")) or 0
                successes_value = _parse_optional_int(row.get("successes"))
                asr_value = _parse_optional_float(row.get("asr"))
                bucket["trials"] = int(bucket["trials"]) + int(trials_value)
                if asr_value is not None:
                    bucket.setdefault("asr_values", []).append(float(asr_value))
                if successes_value is None and asr_value is not None and trials_value:
                    successes_value = int(round(float(asr_value) * float(trials_value)))
                if successes_value is not None:
                    bucket["successes"] = float(bucket.get("successes", 0.0)) + float(successes_value)
    except OSError:
        return []

    results: list[dict[str, object]] = []
    for bucket in aggregates.values():
        trials_total = int(bucket.get("trials", 0))
        successes_total = float(bucket.get("successes", 0.0))
        asr_candidates = [value for value in bucket.get("asr_values", []) if isinstance(value, (int, float))]
        if trials_total > 0:
            asr = successes_total / float(trials_total)
        elif asr_candidates:
            asr = float(sum(asr_candidates)) / float(len(asr_candidates))
        else:
            asr = 0.0
        asr = max(0.0, min(asr, 1.0))
        results.append(
            {
                "id": bucket["id"],
                "value": asr,
                "trials": trials_total,
                "successes": int(round(successes_total)),
                "order": bucket.get("order", 0),
            }
        )

    results.sort(key=lambda item: item.get("order", 0))
    return results


def _extract_slice_labels(
    meta: Mapping[str, object],
    report: Mapping[str, object],
    run_dir: Path,
    slice_ids: Iterable[str],
) -> dict[str, str]:
    targets = {sid for sid in slice_ids if sid}
    if not targets:
        return {}
    labels: dict[str, str] = {}

    def register(slice_id: object, description: object) -> None:
        sid = _normalise_text(slice_id)
        if not sid or sid not in targets:
            return
        if sid in labels:
            return
        desc = _normalise_text(description)
        if not desc:
            return
        labels[sid] = desc

    def register_collection(collection: object) -> None:
        if isinstance(collection, Mapping):
            for key, value in collection.items():
                if isinstance(value, Mapping):
                    candidate_id = value.get("id") or value.get("slice_id") or value.get("exp_id") or value.get("exp") or key
                    candidate_desc = (
                        value.get("description")
                        or value.get("summary")
                        or value.get("label")
                        or value.get("title")
                        or value.get("task")
                    )
                    metadata = value.get("metadata")
                    if not candidate_desc and isinstance(metadata, Mapping):
                        candidate_desc = metadata.get("description") or metadata.get("summary")
                    register(candidate_id, candidate_desc)
                else:
                    register(key, value)
        elif isinstance(collection, list):
            for item in collection:
                if isinstance(item, Mapping):
                    candidate_id = (
                        item.get("id")
                        or item.get("slice_id")
                        or item.get("exp_id")
                        or item.get("exp")
                        or item.get("name")
                    )
                    candidate_desc = (
                        item.get("description")
                        or item.get("summary")
                        or item.get("label")
                        or item.get("title")
                        or item.get("task")
                    )
                    metadata = item.get("metadata")
                    if not candidate_desc and isinstance(metadata, Mapping):
                        candidate_desc = metadata.get("description") or metadata.get("summary")
                    register(candidate_id, candidate_desc)
                else:
                    register(None, item)

    for key in ("slices", "slice_summaries", "slice_summary", "threat_model_slices"):
        register_collection(meta.get(key))
    threat_model_meta = meta.get("threat_model")
    if isinstance(threat_model_meta, Mapping):
        register_collection(threat_model_meta.get("slices"))
    threat_model_report = report.get("threat_model") if isinstance(report, Mapping) else None
    if isinstance(threat_model_report, Mapping):
        register_collection(threat_model_report.get("slices"))

    rows_path, _ = _resolve_rows_path(run_dir, report)
    if rows_path is not None:
        try:
            with rows_path.open("r", encoding="utf-8") as handle:
                for index, line in enumerate(handle):
                    if len(labels) >= len(targets):
                        break
                    if index > 2000:  # safeguard for extremely large files
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    event = _normalise_text(payload.get("event"))
                    if event and event not in {"trial", "case", "row"}:
                        continue
                    sid = (
                        payload.get("slice_id")
                        or payload.get("exp_id")
                        or payload.get("slice")
                        or payload.get("exp")
                    )
                    desc = (
                        payload.get("slice_description")
                        or payload.get("description")
                        or payload.get("task")
                        or payload.get("input_case")
                    )
                    register(sid, desc)
        except OSError:
            pass

    return labels


def build_summary_chart(run_dir: Path, report: dict[str, object], meta: Mapping[str, object]) -> str:
    chart_rows = _summarise_chart_rows(run_dir)
    if not chart_rows:
        return "<p><em>No summary data available for charting.</em></p>"
    slice_ids = [row["id"] for row in chart_rows]
    label_map = _extract_slice_labels(meta, report, run_dir, slice_ids)
    bars: list[str] = []
    for item in chart_rows:
        slice_id = item["id"]
        label_text = label_map.get(slice_id) or slice_id or "Slice"
        safe_label = html.escape(label_text)
        percent = max(0.0, min(float(item.get("value", 0.0)) * 100.0, 100.0))
        height = percent
        fill_classes = "chart-bar-fill"
        if height <= 0.0:
            fill_classes += " chart-bar-zero"
        trials = int(item.get("trials", 0))
        successes = int(item.get("successes", 0))
        title = (
            f"{slice_id}: {successes} success(es) / {trials} trial(s)"
            if trials
            else f"{slice_id}: {percent:.1f}% ASR"
        )
        bars.append(
            "<div class='chart-bar' title='{title}'>"
            "<div class='chart-bar-column'>"
            "<div class='{fill_cls}' style='height: {height:.2f}%;'></div>"
            "</div>"
            "<div class='chart-bar-value'>{percent:.1f}%</div>"
            "<div class='chart-bar-label'>{label}</div>"
            "</div>".format(
                title=html.escape(title),
                fill_cls=fill_classes,
                height=height,
                percent=percent,
                label=safe_label,
            )
        )

    return "<div class='chart-card'><div class='chart-bars'>" + "".join(bars) + "</div></div>"


def build_trial_table(run_dir: Path, report: dict[str, object]) -> str:
    rows_path, rel_href = _resolve_rows_path(run_dir, report)
    if rows_path is None:
        return "<p><em>No rows.jsonl found for this run.</em></p>"
    trial_rows: list[dict[str, str]] = []
    more_available = False
    try:
        with rows_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if len(trial_rows) >= 50:
                    more_available = True
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    payload_raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload_raw, dict):
                    continue
                payload: Mapping[str, object] = payload_raw
                event = _normalise_text(payload.get("event"))
                if event in {"header", "summary"}:
                    continue
                trial_number = _normalise_text(payload.get("trial")) or str(len(trial_rows) + 1)
                slice_id = _normalise_text(
                    payload.get("slice_id")
                    or payload.get("exp_id")
                    or payload.get("slice")
                    or payload.get("exp")
                )
                attack_id = _normalise_text(
                    payload.get("attack_id")
                    or payload.get("attack")
                    or payload.get("attack_name")
                    or payload.get("input_case")
                )
                input_text = _extract_from_keys(
                    payload,
                    (
                        "input",
                        "prompt",
                        "user",
                        "request",
                        "attack_prompt",
                        "messages",
                        "conversation",
                        "question",
                    ),
                )
                output_text = _extract_from_keys(
                    payload,
                    (
                        "output",
                        "response",
                        "model_output",
                        "completion",
                        "answer",
                        "text",
                        "content",
                        "response_text",
                    ),
                )
                success_value = _format_success(payload.get("success"))
                trial_rows.append(
                    {
                        "trial": trial_number or "–",
                        "slice_id": slice_id or "–",
                        "attack_id": attack_id or "–",
                        "input": input_text or "–",
                        "output": output_text or "–",
                        "success": success_value,
                    }
                )
    except OSError:
        return "<p><em>rows.jsonl could not be read.</em></p>"

    if not trial_rows:
        return "<p><em>No trial rows available to display.</em></p>"

    header_cells = "".join(
        f"<th>{label}</th>"
        for label in ("trial", "slice_id", "attack_id", "input (truncated)", "output (truncated)", "success")
    )
    body_rows: list[str] = []
    for row in trial_rows:
        body_rows.append(
            "<tr>"
            + "".join(
                f"<td>{html.escape(_truncate_text(row[key]))}</td>"
                for key in ("trial", "slice_id", "attack_id", "input", "output", "success")
            )
            + "</tr>"
        )

    note_bits = [f"Showing first {len(trial_rows)} trial rows (max 50)."]
    if more_available:
        note_bits.append("Additional rows are available in rows.jsonl.")
    note_html = f"<p class='trial-note'>{' '.join(html.escape(bit) for bit in note_bits)}</p>"
    link_html = (
        f"<p class='trial-link'><a href='{html.escape(rel_href)}'>See full rows.jsonl</a></p>"
        if rel_href
        else ""
    )

    table_html = (
        "<table class='trial-table'><thead><tr>"
        + header_cells
        + "</tr></thead><tbody>"
        + "".join(body_rows)
        + "</tbody></table>"
    )
    return "<div class='trial-table-block'>" + note_html + table_html + link_html + "</div>"


def build_table(headers: list[str], rows: Iterable[dict[str, str]]) -> str:
    iterator = iter(rows)
    try:
        first_row = next(iterator)
    except StopIteration:
        return "<p><em>No rows in summary.csv</em></p>"

    display_headers = list(headers) if headers else list(first_row.keys())
    thead = "".join(f"<th>{html.escape(head)}</th>" for head in display_headers)
    body: list[str] = []
    for record in chain([first_row], iterator):
        cells = "".join(
            f"<td>{html.escape(str(record.get(head, '')))}</td>"
            for head in display_headers
        )
        body.append(f"<tr>{cells}</tr>")
    return (
        "<table class='summary-table'><thead><tr>"
        + thead
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def resolve_run_dir(path: Path) -> Path:
    """Resolve symlinks and fallback pointer files like results/LATEST.path."""

    resolved = path.resolve(strict=False)
    if resolved.exists():
        return resolved
    pointer = path.parent / f"{path.name}.path"
    if pointer.exists():
        target = Path(pointer.read_text(encoding="utf-8").strip())
        if target.exists():
            try:
                return target.resolve()
            except Exception:
                return target
    return resolved


def _default_report_payload() -> dict[str, object]:
    return {
        "total_trials": 0,
        "pre_denied": 0,
        "called_trials": 0,
        "passed_trials": 0,
        "pass_rate": {"display": "0.0%", "percent": 0.0},
        "latency_ms": {"p50": None, "p95": None},
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "cost_present": False,
        "post_warn": 0,
        "post_deny": 0,
        "gates": {
            "pre": {"allow": 0, "warn": 0, "deny": 0},
            "post": {"allow": 0, "warn": 0, "deny": 0},
        },
        "top_reason": "-",
        "reason_counts": {},
        "reason_counts_by_decision": {
            "allow": {},
            "warn": {},
            "deny": {},
        },
        "rows_paths": [],
        "run_json_paths": [],
        "policy_ids": [],
        "encountered_rows_file": False,
        "has_row_data": False,
        "usage": {
            "trials_total": 0,
            "calls_attempted": 0,
            "calls_made": 0,
            "tokens_prompt_sum": 0,
            "tokens_completion_sum": 0,
            "tokens_total_sum": 0,
        },
        "budget": {
            "stopped_early": False,
            "budget_hit": "none",
        },
    }


def load_run_report(run_dir: Path) -> dict[str, object]:
    payload = _default_report_payload()
    report_path = run_dir / REPORT_JSON_NAME
    if not report_path.exists():
        return payload
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return payload
    if isinstance(data, dict):
        for key, value in data.items():
            payload[key] = value
    return payload


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        try:
            return int(float(value))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off"}:
            return False
    return default


def _format_tokens(value: object) -> str:
    tokens = _as_int(value, default=0)
    return f"{tokens:,}"


def _format_cost(report: dict[str, object]) -> str:
    if not report.get("cost_present"):
        return "–"
    try:
        cost_value = float(report.get("estimated_cost_usd", 0.0))
    except (TypeError, ValueError):
        return "–"
    return f"${cost_value:.2f}"


def _pass_rate_display(report: dict[str, object]) -> str:
    pass_rate = report.get("pass_rate")
    if isinstance(pass_rate, dict):
        display = pass_rate.get("display")
        if display:
            return str(display)
    return "0.0%"


def build_status_banner(report: dict[str, object]) -> str:
    thresholds = report.get("thresholds")
    if isinstance(thresholds, dict):
        status = str(thresholds.get("status") or "").upper()
        summary = str(thresholds.get("summary") or "").strip()
        policy = str(thresholds.get("policy") or "").strip()
        strict_flag = thresholds.get("strict")
        css_class = {
            "OK": "status-ok",
            "WARN": "status-warn",
            "FAIL": "status-fail",
        }.get(status, "status-neutral")
        if not summary:
            summary = f"THRESHOLDS: {status or 'UNKNOWN'}"
        title_bits: list[str] = []
        if policy:
            title_bits.append(f"policy={policy}")
        if isinstance(strict_flag, bool):
            title_bits.append(f"strict={'1' if strict_flag else '0'}")
        title_attr = f" title=\"{html.escape('; '.join(title_bits))}\"" if title_bits else ""
        return (
            f"<div class='status-banner {css_class}'{title_attr}>"
            f"{html.escape(summary)}"
            "</div>"
        )
    return "<div class='status-banner status-neutral'>No thresholds evaluated.</div>"


def build_quick_panels(report: dict[str, object]) -> str:
    total = _as_int(report.get("total_trials"), 0)
    callable_trials = _as_int(report.get("callable_trials"), _as_int(report.get("called_trials"), 0))
    pre_denied = _as_int(report.get("pre_denied"), 0)
    passed = _as_int(report.get("passed_trials"), 0)
    pass_rate_display = _pass_rate_display(report)
    callable_context = f"Callable trials: {callable_trials}"
    if total and pre_denied:
        callable_context += f" · Pre-denied: {pre_denied}"
    pass_context = f"Pass rate (callable): {pass_rate_display}"
    if callable_trials:
        pass_context += f" · {passed}/{callable_trials}"
    return f"""
<div class='quick-panels'>
  <div class='quick-card'>
    <div class='quick-title'>Trials</div>
    <div class='quick-value'>{total}</div>
    <div class='quick-context'>{html.escape(callable_context)}</div>
  </div>
  <div class='quick-card'>
    <div class='quick-title'>Pass outcomes</div>
    <div class='quick-value'>{passed}</div>
    <div class='quick-context'>{html.escape(pass_context)}</div>
  </div>
</div>
"""


def _format_latency(report: dict[str, object]) -> str:
    latency = report.get("latency_ms")
    if not isinstance(latency, dict):
        return "–"
    p50 = latency.get("p50")
    p95 = latency.get("p95")
    if p50 is None and p95 is None:
        return "–"
    left = f"{_as_int(p50, 0)} ms" if p50 is not None else "–"
    right = f"{_as_int(p95, 0)} ms" if p95 is not None else "–"
    return f"{left} / {right}"


def build_overview(report: dict[str, object]) -> str:
    passed = _as_int(report.get("passed_trials"), 0)
    called = _as_int(report.get("called_trials"), 0)
    total = _as_int(report.get("total_trials"), 0)
    pass_rate_display = _pass_rate_display(report)
    usage = report.get("usage") if isinstance(report.get("usage"), dict) else {}
    budget = report.get("budget") if isinstance(report.get("budget"), dict) else {}
    tokens_total_sum = _as_int(usage.get("tokens_total_sum") if isinstance(usage, dict) else 0,
                               _as_int(report.get("total_tokens"), 0))
    tokens_display = _format_tokens(tokens_total_sum)
    latency_display = _format_latency(report)
    cost_display = _format_cost(report)
    gates = report.get("gates")
    if not isinstance(gates, dict):
        gates = {}
    pre = gates.get("pre") if isinstance(gates, dict) else {}
    post = gates.get("post") if isinstance(gates, dict) else {}
    if not isinstance(pre, dict):
        pre = {}
    if not isinstance(post, dict):
        post = {}
    pre_text = f"{_as_int(pre.get('allow'), 0)}/{_as_int(pre.get('warn'), 0)}/{_as_int(pre.get('deny'), 0)}"
    post_text = f"{_as_int(post.get('allow'), 0)}/{_as_int(post.get('warn'), 0)}/{_as_int(post.get('deny'), 0)}"
    post_warn = _as_int(report.get("post_warn"), 0)
    post_deny = _as_int(report.get("post_deny"), 0)
    top_reason = str(report.get("top_reason") or "-")
    calls_made = _as_int(usage.get("calls_made") if isinstance(usage, dict) else 0, called)
    budget_hit = str((budget.get("budget_hit") if isinstance(budget, dict) else "") or "none")
    stopped_early = _as_bool(budget.get("stopped_early") if isinstance(budget, dict) else None, budget_hit.lower() != "none")
    gate_summary = gates.get("summary") if isinstance(gates, dict) else {}
    if isinstance(gate_summary, dict):
        pre_top_decision = str(gate_summary.get("pre_decision") or "-")
        pre_top_reason = str(gate_summary.get("pre_reason") or "-")
        post_top_decision = str(gate_summary.get("post_decision") or "-")
        post_top_reason = str(gate_summary.get("post_reason") or "-")
    else:
        pre_top_decision = post_top_decision = "-"
        pre_top_reason = post_top_reason = "-"
    mode_display = str(gates.get("mode") or "").strip().upper() if isinstance(gates, dict) else ""
    if not mode_display:
        mode_display = "ALLOW"
    version_display = str(gates.get("version") or "").strip() if isinstance(gates, dict) else ""
    gate_meta_line = f"mode {mode_display}"
    if version_display:
        gate_meta_line += f" · v{version_display}"
    top_parts: list[str] = []
    if pre_top_decision and pre_top_decision != "-":
        pre_piece = pre_top_decision.upper()
        if pre_top_reason and pre_top_reason != "-":
            pre_piece += f" ({pre_top_reason})"
        top_parts.append(f"pre {pre_piece}")
    if post_top_decision and post_top_decision != "-":
        post_piece = post_top_decision.upper()
        if post_top_reason and post_top_reason != "-":
            post_piece += f" ({post_top_reason})"
        top_parts.append(f"post {post_piece}")
    gate_sub_parts = [gate_meta_line, f"post warn/deny: {post_warn}/{post_deny}"]
    if top_parts:
        gate_sub_parts.append(" · ".join(top_parts))
    gate_subline = " · ".join(gate_sub_parts)
    budget_line = (
        "<div class='overview-budget'>Budget: calls {calls} | tokens {tokens} | "
        "stopped_early {stopped} | hit {hit}</div>"
    ).format(
        calls=calls_made,
        tokens=html.escape(tokens_display),
        stopped=str(stopped_early).lower(),
        hit=html.escape(budget_hit),
    )
    return f"""
<div class='overview-grid'>
  <div class='overview-card overview-pass'>
    <div class='label'>Pass rate</div>
    <div class='value'>{html.escape(pass_rate_display)}</div>
    <div class='sub'>{html.escape(f"{passed}/{called}")}</div>
  </div>
  <div class='overview-card'>
    <div class='label'>Trials</div>
    <div class='value'>{html.escape(f"{called} of {total}")}</div>
  </div>
  <div class='overview-card'>
    <div class='label'>Latency (p50/p95)</div>
    <div class='value'>{html.escape(latency_display)}</div>
  </div>
  <div class='overview-card'>
    <div class='label'>Tokens</div>
    <div class='value'>{html.escape(tokens_display)}</div>
  </div>
  <div class='overview-card'>
    <div class='label'>Cost</div>
    <div class='value'>{html.escape(cost_display)}</div>
  </div>
  <div class='overview-card'>
    <div class='label'>Governance decisions</div>
    <div class='value'>pre allow/warn/deny: {html.escape(pre_text)} · post allow/warn/deny: {html.escape(post_text)}</div>
    <div class='sub'>{html.escape(gate_subline)}</div>
  </div>
  <div class='overview-card'>
    <div class='label'>Top reason</div>
    <div class='value'>{html.escape(top_reason)}</div>
  </div>
</div>
{budget_line}
"""


def build_overview_badge(report: dict[str, object]) -> str:
    budget = report.get("budget") if isinstance(report.get("budget"), dict) else {}
    hit = str((budget.get("budget_hit") if isinstance(budget, dict) else "") or "none")
    stopped = _as_bool(budget.get("stopped_early") if isinstance(budget, dict) else None, hit.lower() != "none")
    if not stopped:
        return ""
    return f"<span class='badge badge-warn'>Stopped early: {html.escape(hit)}</span>"


def build_threshold_badge(report: dict[str, object]) -> str:
    thresholds = report.get("thresholds")
    if not isinstance(thresholds, dict):
        return ""
    status = str(thresholds.get("status") or "").upper()
    summary = str(thresholds.get("summary") or "").strip()
    policy = str(thresholds.get("policy") or "").strip()
    strict_flag = thresholds.get("strict")

    css_class = {
        "OK": "badge-ok",
        "WARN": "badge-warn",
        "FAIL": "badge-fail",
    }.get(status, "badge-warn")

    title_bits: list[str] = []
    if policy:
        title_bits.append(f"policy={policy}")
    if isinstance(strict_flag, bool):
        title_bits.append(f"strict={'1' if strict_flag else '0'}")
    title_attr = f" title=\"{html.escape('; '.join(title_bits))}\"" if title_bits else ""

    if not summary:
        summary = f"THRESHOLDS: {status or 'UNKNOWN'}"

    return f"<span class='badge {css_class}'{title_attr}>{html.escape(summary)}</span>"


def build_evaluator_panel(report: dict[str, object]) -> str:
    evaluator = report.get("evaluator") if isinstance(report.get("evaluator"), dict) else None
    if not isinstance(evaluator, dict):
        return "<p><em>No evaluator metadata recorded.</em></p>"
    version = str(evaluator.get("version") or "–")
    rules_total = evaluator.get("rules_total")
    rules_total_text = "–"
    if isinstance(rules_total, (int, float)):
        try:
            rules_total_text = str(int(rules_total))
        except (TypeError, ValueError):
            rules_total_text = str(rules_total)
    elif isinstance(rules_total, str) and rules_total.strip():
        rules_total_text = rules_total.strip()
    rule_ids = evaluator.get("active_rule_ids")
    if isinstance(rule_ids, list):
        tokens = [str(item).strip() for item in rule_ids if str(item).strip()]
        rule_text = ", ".join(tokens) if tokens else "–"
    else:
        rule_text = "–"
    callable_trials = _as_int(
        evaluator.get("callable_trials"),
        _as_int(report.get("callable_trials"), 0),
    )
    successes = _as_int(
        evaluator.get("successes"),
        _as_int(report.get("passed_trials"), 0),
    )
    pass_rate_display = ""
    rate_info = evaluator.get("pass_rate") if isinstance(evaluator.get("pass_rate"), dict) else None
    if isinstance(rate_info, dict):
        display = rate_info.get("display")
        if display:
            pass_rate_display = str(display)
    if not pass_rate_display:
        overall_rate = report.get("pass_rate") if isinstance(report.get("pass_rate"), dict) else None
        if isinstance(overall_rate, dict):
            display = overall_rate.get("display")
            if display:
                pass_rate_display = str(display)
    if not pass_rate_display:
        pass_rate_display = "0.0%"
    config_path = str(evaluator.get("config_path") or "").strip()
    ratio_text = f"{successes}/{callable_trials}" if callable_trials else f"{successes}/0"
    items = [
        "<div class='item'><span class='label'>Version:</span> "
        + f"<span class='value'>{html.escape(version)}</span>"
        + f"<span class='meta'>(rules: {html.escape(rules_total_text)})</span></div>",
        "<div class='item'><span class='label'>Active rule(s):</span> "
        + f"<span class='value'>{html.escape(rule_text)}</span></div>",
        "<div class='item'><span class='label'>Callable trials:</span> "
        + f"<span class='value'>{callable_trials}</span></div>",
        "<div class='item'><span class='label'>Successes:</span> "
        + f"<span class='value'>{successes}</span></div>",
        "<div class='item'><span class='label'>Pass rate:</span> "
        + f"<span class='value'>{html.escape(pass_rate_display)}</span>"
        + f"<span class='meta'>({html.escape(ratio_text)})</span></div>",
    ]
    if config_path:
        items.append(
            "<div class='item'><span class='label'>Rules file:</span> "
            + f"<span class='value'>{html.escape(config_path)}</span></div>"
        )
    return "<div class='evaluator-panel'>" + "".join(items) + "</div>"


def _clean_status_message(kind: str, message: str) -> str:
    prefix = f"RUN {kind.upper()}:"
    text = message.strip()
    if text.upper().startswith(prefix):
        body = text[len(prefix) :].strip()
        if body:
            return body[:1].upper() + body[1:]
        return body
    return text


def build_banners(report: dict[str, object], policy_ids: list[object]) -> str:
    banners: list[str] = []
    total_trials = _as_int(report.get("total_trials"), 0)
    called_trials = _as_int(report.get("called_trials"), 0)
    encountered = bool(report.get("encountered_rows_file"))
    has_data = bool(report.get("has_row_data"))

    status = report.get("status") if isinstance(report.get("status"), dict) else None
    status_kind = ""
    status_message = ""
    if isinstance(status, dict):
        status_kind = str(status.get("kind") or "").lower()
        raw_message = str(status.get("message") or "")
        if raw_message:
            status_message = _clean_status_message(status_kind, raw_message)

    added_error = False
    added_warn = False

    if not encountered or not has_data:
        message = status_message if status_kind == "fail" and status_message else "No data rows found for this run."
        banners.append(
            f"<div class='banner banner-error'>{html.escape(message)}</div>"
        )
        added_error = True
    elif total_trials > 0 and called_trials == 0:
        if status_kind == "warn" and status_message:
            warn_message = status_message
        else:
            policy_text = "unknown"
            if policy_ids:
                policy_text = str(policy_ids[0])
            warn_message = (
                "All trials denied by pre-gate (policy: "
                f"{policy_text}). No model calls were made."
            )
        banners.append(
            f"<div class='banner banner-warn'>{html.escape(warn_message)}</div>"
        )
        added_warn = True

    if status_kind == "fail" and not added_error and status_message:
        banners.append(
            f"<div class='banner banner-error'>{html.escape(status_message)}</div>"
        )
    elif status_kind == "warn" and not added_warn and status_message:
        banners.append(
            f"<div class='banner banner-warn'>{html.escape(status_message)}</div>"
        )

    return "\n".join(banners)


def build_reason_table(report: dict[str, object]) -> str:
    breakdown_raw = report.get("reason_counts_by_decision")
    breakdown: dict[str, dict[str, int]] = {}
    if isinstance(breakdown_raw, dict):
        for decision, mapping in breakdown_raw.items():
            if not isinstance(mapping, dict):
                continue
            cleaned: dict[str, int] = {}
            for reason, count in mapping.items():
                text = str(reason)
                cleaned[text] = _as_int(count, 0)
            breakdown[decision] = cleaned

    if not any(breakdown.get(key) for key in ("allow", "warn", "deny")):
        reasons = report.get("reason_counts")
        if isinstance(reasons, dict) and reasons:
            breakdown["deny"] = {
                str(reason): _as_int(count, 0) for reason, count in reasons.items()
            }
        else:
            return "<p><em>No gate reason codes recorded.</em></p>"

    display_order = [
        ("deny", "Deny", "reason-card-deny"),
        ("warn", "Warn", "reason-card-warn"),
        ("allow", "Allow", "reason-card-allow"),
    ]

    cards: list[str] = []
    for key, label, css_class in display_order:
        bucket = breakdown.get(key, {}) or {}
        total = sum(int(value) for value in bucket.values())
        if not bucket:
            body = "<li><em>None recorded</em></li>"
        else:
            ordered = sorted(
                ((reason, int(count)) for reason, count in bucket.items()),
                key=lambda item: (-item[1], item[0]),
            )
            top_three = ordered[:3]
            body = "".join(
                f"<li><span class='code'>{html.escape(reason)}</span><span class='count'>{count}</span></li>"
                for reason, count in top_three
            )
        cards.append(
            "<div class='reason-card {css_class}'>".format(css_class=css_class)
            + f"<div class='reason-title'>{label}</div>"
            + f"<div class='reason-total'>Total: {total}</div>"
            + f"<ul>{body}</ul>"
            + "</div>"
        )

    legend = "<p class='reason-legend'>pre = before calling model; post = after</p>"
    return legend + "<div class='reason-grid'>" + "".join(cards) + "</div>"


def build_data_links(run_dir: Path, report: dict[str, object]) -> str:
    summary_path = run_dir / "summary.csv"
    if summary_path.exists():
        summary_html = "Summary: <a href='summary.csv' download>summary.csv</a>"
    else:
        summary_html = "<span class='missing'>summary.csv (missing)</span>"

    rows_paths = report.get("rows_paths")
    row_links: list[str] = []
    if isinstance(rows_paths, list) and rows_paths:
        for rel_path in rows_paths:
            rel_text = str(rel_path)
            if not rel_text:
                continue
            escaped = html.escape(rel_text)
            row_links.append(f"<a href='{escaped}' download>Download {escaped}</a>")
    else:
        default_rows = run_dir / "rows.jsonl"
        if default_rows.exists():
            row_links.append("<a href='rows.jsonl' download>Download rows.jsonl</a>")

    if not row_links:
        rows_html = "<span class='missing'>rows.jsonl (missing)</span>"
    else:
        rows_html = "Rows: " + " · ".join(row_links)

    return (
        "<div class='data-links'>"
        + f"<span>{summary_html}</span>"
        + f"<span>{rows_html}</span>"
        + "</div>"
    )


def build_artifact_links(run_dir: Path, report: dict[str, object]) -> str:
    items: list[str] = []
    for name in ("summary.csv", "summary.svg", REPORT_JSON_NAME, "run.json"):
        candidate = run_dir / name
        if candidate.exists():
            items.append(f"<li><a href='{html.escape(name)}'>{html.escape(name)}</a></li>")
        else:
            items.append(
                f"<li><span class='missing'>{html.escape(name)} (missing)</span></li>"
            )
    rows_paths = report.get("rows_paths")
    if isinstance(rows_paths, list) and rows_paths:
        links = ", ".join(
            f"<a href='{html.escape(str(path))}'>{html.escape(str(path))}</a>"
            for path in rows_paths
        )
        items.append(f"<li><strong>rows.jsonl:</strong> {links}</li>")
    else:
        items.append("<li><strong>rows.jsonl:</strong> <em>not found</em></li>")
    run_json_paths = report.get("run_json_paths")
    if isinstance(run_json_paths, list) and run_json_paths:
        links = ", ".join(
            f"<a href='{html.escape(str(path))}'>{html.escape(str(path))}</a>"
            for path in run_json_paths
        )
        items.append(f"<li><strong>run.json:</strong> {links}</li>")
    else:
        items.append("<li><strong>run.json:</strong> <em>not found</em></li>")
    return "<ul class='artifact-list'>" + "".join(items) + "</ul>"


def render_template(context: dict[str, str]) -> str:
    if TEMPLATE_PATH.exists():
        template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    else:
        template_text = """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>$TITLE</title>
    <style>
      body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;background:#f9fafb;color:#1f2933;}
      h1{margin:0 0 16px;font-size:26px;}
      h2{margin:32px 0 12px;font-size:20px;}
      .meta{color:#52606d;font-size:13px;margin:4px 0 16px;}
      .status-banner{display:inline-flex;align-items:center;padding:10px 18px;border-radius:999px;font-weight:600;font-size:14px;margin:0 0 16px;}
      .status-ok{background:#dcfce7;color:#166534;}
      .status-warn{background:#fef3c7;color:#92400e;}
      .status-fail{background:#fee2e2;color:#b91c1c;}
      .status-neutral{background:#e5e7eb;color:#374151;}
      .banner{padding:12px 16px;border-radius:6px;margin-bottom:16px;font-size:14px;}
      .banner-error{background:#fee2e2;color:#b91c1c;}
      .banner-warn{background:#fef3c7;color:#92400e;}
      .quick-panels{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:16px;}
      .quick-card{background:#ffffff;padding:12px 16px;border-radius:10px;box-shadow:0 1px 2px rgba(15,23,42,0.08);flex:1 1 220px;min-width:220px;}
      .quick-title{font-size:12px;text-transform:uppercase;letter-spacing:0.08em;color:#52606d;}
      .quick-value{font-size:24px;font-weight:600;color:#1f2933;margin-top:4px;}
      .quick-context{font-size:14px;color:#52606d;margin-top:6px;}
      .overview-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;}
      .overview-header{display:flex;align-items:center;gap:10px;margin-bottom:8px;}
      .overview-header h2{margin:0;}
      .overview-card{background:#ffffff;padding:12px 16px;border-radius:8px;box-shadow:0 1px 2px rgba(15,23,42,0.08);}
      .overview-pass{background:#1e293b;color:#f8fafc;}
      .overview-card .label{font-size:12px;text-transform:uppercase;letter-spacing:0.06em;color:inherit;opacity:0.7;}
      .overview-card .value{font-size:20px;font-weight:600;margin-top:4px;}
      .overview-card .sub{font-size:13px;margin-top:2px;opacity:0.8;}
      .evaluator-panel{background:#ffffff;padding:12px 16px;border-radius:8px;box-shadow:0 1px 2px rgba(15,23,42,0.08);margin:16px 0;}
      .evaluator-panel .item{font-size:14px;margin:4px 0;color:#1f2933;}
      .evaluator-panel .label{font-weight:600;margin-right:4px;}
      .evaluator-panel .meta{color:#52606d;font-size:12px;margin-left:6px;}
      .badge{display:inline-flex;align-items:center;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:600;}
      .badge-ok{background:#dcfce7;color:#166534;}
      .badge-warn{background:#fef3c7;color:#92400e;}
      .badge-fail{background:#fee2e2;color:#b91c1c;}
      .overview-budget{margin-top:10px;font-size:14px;color:#52606d;}
      .reason-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:16px 0;}
      .reason-card{background:#ffffff;padding:14px 16px;border-radius:10px;box-shadow:0 1px 2px rgba(15,23,42,0.08);border-top:3px solid transparent;}
      .reason-card-deny{border-color:#b91c1c;}
      .reason-card-warn{border-color:#d97706;}
      .reason-card-allow{border-color:#166534;}
      .reason-title{font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#52606d;}
      .reason-total{font-size:13px;color:#52606d;margin-top:4px;}
      .reason-card ul{list-style:none;margin:10px 0 0;padding:0;}
      .reason-card li{display:flex;justify-content:space-between;font-size:14px;padding:4px 0;border-bottom:1px solid #e5e7eb;}
      .reason-card li:last-child{border-bottom:none;}
      .reason-card .code{font-weight:600;color:#1f2933;}
      .reason-card .count{color:#52606d;}
      .data-links{display:flex;flex-wrap:wrap;gap:16px;margin:0 0 16px;font-size:14px;}
      .data-links span{display:inline-flex;align-items:center;gap:8px;}
      table{border-collapse:collapse;width:100%;max-width:980px;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 2px rgba(15,23,42,0.08);}
      th,td{border:1px solid #e5e7eb;padding:8px 10px;font-size:14px;text-align:left;}
      th{background:#f3f4f6;font-weight:600;}
      .artifact-list{list-style:none;padding:0;margin:0;}
      .artifact-list li{margin:4px 0;}
      .missing{color:#9ca3af;}
      a{color:#2563eb;text-decoration:none;}
      a:hover{text-decoration:underline;}
      $INLINE_CHART_CSS
    </style>
  </head>
  <body>
    <h1>$HEADER_TITLE</h1>
    $META
    $STATUS_BANNER
    $QUICK_PANELS
    $DATA_LINKS
    $BANNERS
    <h2>Why were decisions made?</h2>
    $TOP_REASONS
    <div class='overview-header'>
      <h2>Overview</h2>
      $THRESHOLD_BADGE
      $OVERVIEW_BADGE
    </div>
    $OVERVIEW
    <h2>Evaluator</h2>
    $EVALUATOR_PANEL
    <h2>Attack result (ASR)</h2>
    $SUMMARY_CHART
    <h2>Summary table</h2>
    $SUMMARY_TABLE
    <h2>Trial I/O</h2>
    $TRIAL_TABLE
    <h2>Artifacts</h2>
    $ARTIFACT_LINKS
  </body>
</html>
"""
    tmpl = Template(template_text)
    return tmpl.safe_substitute(context)


def write_report(run_dir: Path) -> None:
    run_dir = resolve_run_dir(run_dir)
    headers, rows = read_rows(run_dir / "summary.csv")
    table_html = build_table(headers, rows)
    meta = load_run_meta(run_dir)
    report = load_run_report(run_dir)
    summary_snapshot = _read_summary_snapshot(run_dir)

    schema = html.escape(str(meta.get("summary_schema", ""))) if meta else ""
    results_schema = html.escape(str(meta.get("results_schema", ""))) if meta else ""
    run_id = html.escape(run_dir.name)

    chart_html = build_summary_chart(run_dir, report, meta)

    meta_parts: list[str] = []
    model_badge = _collect_model_badge(meta, summary_snapshot)
    seed_badge = _collect_seed_badges(meta, summary_snapshot)
    meta_parts.append(f"<div><strong>Model:</strong> {html.escape(model_badge)}</div>")
    meta_parts.append(f"<div><strong>Seed:</strong> {html.escape(seed_badge)}</div>")
    if run_id:
        meta_parts.append(f"<div><strong>Run:</strong> {run_id}</div>")
    if schema:
        meta_parts.append(f"<div><strong>summary_schema:</strong> {schema}</div>")
    if results_schema:
        meta_parts.append(f"<div><strong>results_schema:</strong> {results_schema}</div>")
    meta_html = "<div class='meta'>" + " · ".join(meta_parts) + "</div>" if meta_parts else ""

    policy_ids = report.get("policy_ids")
    if not isinstance(policy_ids, list):
        policy_ids = []

    context = {
        "TITLE": f"DoomArena-Lab Run Report — {run_id}" if run_id else "DoomArena-Lab Run Report",
        "HEADER_TITLE": "DoomArena-Lab Run Report",
        "META": meta_html,
        "STATUS_BANNER": build_status_banner(report),
        "QUICK_PANELS": build_quick_panels(report),
        "DATA_LINKS": build_data_links(run_dir, report),
        "BANNERS": build_banners(report, policy_ids),
        "THRESHOLD_BADGE": build_threshold_badge(report),
        "OVERVIEW_BADGE": build_overview_badge(report),
        "OVERVIEW": build_overview(report),
        "EVALUATOR_PANEL": build_evaluator_panel(report),
        "SUMMARY_CHART": chart_html,
        "SUMMARY_TABLE": table_html,
        "TOP_REASONS": build_reason_table(report),
        "ARTIFACT_LINKS": build_artifact_links(run_dir, report),
        "TRIAL_TABLE": build_trial_table(run_dir, report),
        "INLINE_CHART_CSS": _load_chart_css(),
    }

    html_doc = render_template(context)
    output = run_dir / "index.html"
    output.write_text(html_doc, encoding="utf-8")
    print(f"Wrote {output}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: mk_report.py <RUN_DIR>")
        return 2
    write_report(Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

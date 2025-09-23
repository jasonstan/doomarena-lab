import csv
import html
import json
import sys
from pathlib import Path
from string import Template


TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "reports" / "templates" / "index.html"
REPORT_JSON_NAME = "run_report.json"


def read_rows(csv_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not csv_path.exists():
        return rows
    with csv_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for record in reader:
            rows.append({(key or "").strip(): (value or "") for key, value in record.items()})
    return rows


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


def build_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "<p><em>No rows in summary.csv</em></p>"
    headers = list(rows[0].keys())
    thead = "".join(f"<th>{html.escape(head)}</th>" for head in headers)
    body: list[str] = []
    for record in rows:
        cells = "".join(
            f"<td>{html.escape(str(record.get(head, '')))}</td>" for head in headers
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
    pass_rate = report.get("pass_rate")
    pass_rate_display = "0.0%"
    if isinstance(pass_rate, dict):
        display = pass_rate.get("display")
        if display:
            pass_rate_display = str(display)
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
    <div class='label'>Gates</div>
    <div class='value'>pre: {html.escape(pre_text)} · post: {html.escape(post_text)}</div>
    <div class='sub'>post warn/deny: {html.escape(f"{post_warn}/{post_deny}")}</div>
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
    reasons = report.get("reason_counts")
    if not isinstance(reasons, dict) or not reasons:
        return "<p><em>No gate reason codes recorded.</em></p>"
    ordered = sorted(
        ((str(reason), _as_int(count, 0)) for reason, count in reasons.items()),
        key=lambda item: (-item[1], item[0]),
    )
    rows_html = [
        f"<tr><td>{html.escape(reason)}</td><td>{count}</td></tr>"
        for reason, count in ordered[:3]
    ]
    return (
        "<table class='reason-table'><thead><tr><th>Reason code</th><th>Count</th></tr></thead><tbody>"
        + "".join(rows_html)
        + "</tbody></table>"
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
      .banner{padding:12px 16px;border-radius:6px;margin-bottom:16px;font-size:14px;}
      .banner-error{background:#fee2e2;color:#b91c1c;}
      .banner-warn{background:#fef3c7;color:#92400e;}
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
      table{border-collapse:collapse;width:100%;max-width:980px;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 2px rgba(15,23,42,0.08);}
      th,td{border:1px solid #e5e7eb;padding:8px 10px;font-size:14px;text-align:left;}
      th{background:#f3f4f6;font-weight:600;}
      .artifact-list{list-style:none;padding:0;margin:0;}
      .artifact-list li{margin:4px 0;}
      .missing{color:#9ca3af;}
      a{color:#2563eb;text-decoration:none;}
      a:hover{text-decoration:underline;}
    </style>
  </head>
  <body>
    <h1>$HEADER_TITLE</h1>
    $META
    $BANNERS
    <div class='overview-header'>
      <h2>Overview</h2>
      $THRESHOLD_BADGE
      $OVERVIEW_BADGE
    </div>
    $OVERVIEW
    <h2>Evaluator</h2>
    $EVALUATOR_PANEL
    <h2>Summary chart</h2>
    $SUMMARY_CHART
    <h2>Summary table</h2>
    $SUMMARY_TABLE
    <h2>Top gate reasons</h2>
    $TOP_REASONS
    <h2>Artifacts</h2>
    $ARTIFACT_LINKS
  </body>
</html>
"""
    tmpl = Template(template_text)
    return tmpl.safe_substitute(context)


def write_report(run_dir: Path) -> None:
    run_dir = resolve_run_dir(run_dir)
    rows = read_rows(run_dir / "summary.csv")
    table_html = build_table(rows)
    meta = load_run_meta(run_dir)
    report = load_run_report(run_dir)

    schema = html.escape(str(meta.get("summary_schema", ""))) if meta else ""
    results_schema = html.escape(str(meta.get("results_schema", ""))) if meta else ""
    run_id = html.escape(run_dir.name)

    svg_rel = "summary.svg"
    svg_tag = (
        f"<object type='image/svg+xml' data='{svg_rel}' width='100%'></object>"
        if (run_dir / svg_rel).exists()
        else "<p><em>summary.svg not found</em></p>"
    )

    meta_parts: list[str] = []
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
        "BANNERS": build_banners(report, policy_ids),
        "THRESHOLD_BADGE": build_threshold_badge(report),
        "OVERVIEW_BADGE": build_overview_badge(report),
        "OVERVIEW": build_overview(report),
        "EVALUATOR_PANEL": build_evaluator_panel(report),
        "SUMMARY_CHART": svg_tag,
        "SUMMARY_TABLE": table_html,
        "TOP_REASONS": build_reason_table(report),
        "ARTIFACT_LINKS": build_artifact_links(run_dir, report),
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

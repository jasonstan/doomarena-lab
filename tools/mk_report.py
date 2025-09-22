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
    tokens_display = _format_tokens(report.get("total_tokens"))
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
"""


def build_banners(report: dict[str, object], policy_ids: list[object]) -> str:
    banners: list[str] = []
    total_trials = _as_int(report.get("total_trials"), 0)
    called_trials = _as_int(report.get("called_trials"), 0)
    encountered = bool(report.get("encountered_rows_file"))
    has_data = bool(report.get("has_row_data"))
    if not encountered or not has_data:
        banners.append(
            "<div class='banner banner-error'>No data rows found for this run.</div>"
        )
    elif total_trials > 0 and called_trials == 0:
        policy_text = "unknown"
        if policy_ids:
            policy_text = str(policy_ids[0])
        banners.append(
            "<div class='banner banner-warn'>All trials denied by pre-gate (policy: "
            f"{html.escape(policy_text)}). No model calls were made.</div>"
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
      .overview-card{background:#ffffff;padding:12px 16px;border-radius:8px;box-shadow:0 1px 2px rgba(15,23,42,0.08);}
      .overview-pass{background:#1e293b;color:#f8fafc;}
      .overview-card .label{font-size:12px;text-transform:uppercase;letter-spacing:0.06em;color:inherit;opacity:0.7;}
      .overview-card .value{font-size:20px;font-weight:600;margin-top:4px;}
      .overview-card .sub{font-size:13px;margin-top:2px;opacity:0.8;}
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
    $OVERVIEW
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
        "OVERVIEW": build_overview(report),
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

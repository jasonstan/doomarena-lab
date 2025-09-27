#!/usr/bin/env python3
"""Generate a minimal HTML report for the MVP demo results."""

from __future__ import annotations

import argparse
import csv
import html
import json
import pathlib
from typing import Any


def _load_rows(path: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _load_summary(path: pathlib.Path) -> dict[str, dict[str, str]]:
    summary: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            attack_id = row.get("attack_id")
            if attack_id:
                summary[attack_id] = row
    return summary


def _load_run_meta(rows_path: pathlib.Path) -> dict[str, Any]:
    run_meta_path = rows_path.parent / "run.json"
    if not run_meta_path.exists():
        return {}
    with run_meta_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _format_percent(value: str | float | None) -> str:
    if value is None:
        return "0%"
    try:
        if isinstance(value, str):
            value = float(value)
        return f"{value * 100:.1f}%"
    except Exception:  # pragma: no cover - defensive conversion
        return "0%"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a minimal HTML report for MVP demo results")
    parser.add_argument("--rows", required=True, type=pathlib.Path)
    parser.add_argument("--summary", required=True, type=pathlib.Path)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    args = parser.parse_args()

    rows = _load_rows(args.rows)
    summary = _load_summary(args.summary)
    run_meta = _load_run_meta(args.rows)

    overall = summary.get("overall", {})

    html_parts: list[str] = []
    html_parts.append("<!DOCTYPE html>")
    html_parts.append("<html><head><meta charset='utf-8'>")
    html_parts.append("<title>DoomArena MVP Demo Report</title>")
    html_parts.append(
        "<style>body{font-family:Arial,Helvetica,sans-serif;margin:20px;}table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #ddd;padding:8px;vertical-align:top;}th{background-color:#f4f4f4;}"
        "button{padding:4px 8px;}pre{white-space:pre-wrap;word-break:break-word;margin:8px 0;}"
        ".success-true{color:#0a0;} .success-false{color:#a00;}</style>"
    )
    html_parts.append(
        "<script>function toggle(id){var el=document.getElementById(id);if(!el){return;}"
        "if(el.style.display==='none'){el.style.display='block';}else{el.style.display='none';}}</script>"
    )
    html_parts.append("</head><body>")
    html_parts.append("<h1>DoomArena MVP Demo Report</h1>")

    provider = html.escape(str(run_meta.get("provider", "unknown")))
    model = html.escape(str(run_meta.get("model", "unknown")))
    temperature = html.escape(str(run_meta.get("temperature", "0")))
    trials = html.escape(str(run_meta.get("trials", "0")))
    timestamp = html.escape(str(run_meta.get("timestamp", "")))

    html_parts.append(
        f"<p><strong>Provider:</strong> {provider} &nbsp; <strong>Model:</strong> {model} &nbsp;"
        f"<strong>Temperature:</strong> {temperature} &nbsp; <strong>Trials per case:</strong> {trials}</p>"
    )
    if timestamp:
        html_parts.append(f"<p><strong>Timestamp:</strong> {timestamp}</p>")

    overall_asr = _format_percent(overall.get("asr"))
    html_parts.append(f"<p><strong>Overall ASR:</strong> {overall_asr}</p>")

    html_parts.append(
        "<table><thead><tr><th>Attempt</th><th>Attack ID</th><th>Success</th><th>Input</th><th>Output</th></tr></thead><tbody>"
    )
    for index, row in enumerate(rows):
        attempt = html.escape(str(row.get("trial_id", index)))
        attack_id = html.escape(str(row.get("attack_id", "")))
        success_value = bool(row.get("success"))
        success_label = "✅" if success_value else "❌"
        success_class = "success-true" if success_value else "success-false"
        input_content = html.escape(row.get("input_text", ""))
        output_content = html.escape(row.get("output_text", ""))
        error_text = html.escape(row.get("error", ""))
        input_id = f"input-{index}"
        output_id = f"output-{index}"
        input_cell = (
            f"<button type='button' onclick=\"toggle('{input_id}')\">Toggle</button>"
            f"<div id='{input_id}' style='display:none;'><pre>{input_content}</pre></div>"
        )
        if error_text:
            output_body = f"<pre>{output_content}</pre><pre>Error: {error_text}</pre>"
        else:
            output_body = f"<pre>{output_content}</pre>"
        output_cell = (
            f"<button type='button' onclick=\"toggle('{output_id}')\">Toggle</button>"
            f"<div id='{output_id}' style='display:none;'>{output_body}</div>"
        )
        html_parts.append(
            "<tr>"
            f"<td>{attempt}</td>"
            f"<td>{attack_id}</td>"
            f"<td class='{success_class}'>{success_label}</td>"
            f"<td>{input_cell}</td>"
            f"<td>{output_cell}</td>"
            "</tr>"
        )
    html_parts.append("</tbody></table>")

    html_parts.append("</body></html>")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(html_parts), encoding="utf-8")


if __name__ == "__main__":
    main()

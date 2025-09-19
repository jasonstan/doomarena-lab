#!/usr/bin/env python3
"""Build a tiny, dependency-free HTML report for a results directory."""
from __future__ import annotations
import csv, json, html, sys
from pathlib import Path

def read_rows(csv_path: Path):
    rows = []
    if not csv_path.exists():
        return rows
    with csv_path.open(newline="") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            rows.append({(k or "").strip(): (v or "") for k, v in r.items()})
    return rows

def load_run_meta(run_dir: Path):
    data = {}
    p = run_dir / "run.json"
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    return data

def build_table(rows):
    if not rows:
        return "<p><em>No rows in summary.csv</em></p>"
    hdrs = list(rows[0].keys())
    thead = "".join(f"<th>{html.escape(h)}</th>" for h in hdrs)
    body = []
    for r in rows:
        tds = "".join(f"<td>{html.escape(str(r.get(h,'')))}</td>" for h in hdrs)
        body.append(f"<tr>{tds}</tr>")
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{''.join(body)}</tbody></table>"


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


def write_report(run_dir: Path):
    run_dir = resolve_run_dir(run_dir)
    rows = read_rows(run_dir / "summary.csv")
    table_html = build_table(rows)
    meta = load_run_meta(run_dir)
    schema = html.escape(str(meta.get("summary_schema", "")))
    results_schema = html.escape(str(meta.get("results_schema", "")))
    run_id = html.escape(run_dir.name)
    svg_rel = "summary.svg"
    svg_tag = (
        f"<object type='image/svg+xml' data='{svg_rel}' width='100%'></object>"
        if (run_dir / svg_rel).exists()
        else "<p><em>summary.svg not found</em></p>"
    )
    meta_rows = []
    if run_id: meta_rows.append(f"<div><strong>Run:</strong> {run_id}</div>")
    if schema: meta_rows.append(f"<div><strong>summary_schema:</strong> {schema}</div>")
    if results_schema: meta_rows.append(f"<div><strong>results_schema:</strong> {results_schema}</div>")
    meta_html = "<div class='meta'>" + " · ".join(meta_rows) + "</div>"

    html_doc = f"""<!doctype html>
    <meta charset="utf-8">
    <title>DoomArena-Lab Run Report — {run_id}</title>
    <style>
      body{{font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin:24px;}}
      h1,h2{{margin:0 0 12px}}
      .meta{{color:#666; font-size:13px; margin:8px 0 16px}}
      table{{border-collapse:collapse; margin-top:8px; width:100%; max-width:980px}}
      th,td{{border:1px solid #ddd; padding:6px 8px; font-size:14px}}
      th{{background:#f6f6f6; text-align:left}}
      code{{background:#f2f2f2; padding:2px 4px; border-radius:4px}}
    </style>
    <h1>DoomArena-Lab Run Report</h1>
    {meta_html}
    <h2>Summary chart</h2>
    {svg_tag}
    <h2>Summary table</h2>
    {table_html}
    <p class="meta">Files: <code>summary.csv</code> · <code>summary.svg</code> · <code>run.json</code></p>
    """
    output = run_dir / "index.html"
    output.write_text(html_doc, encoding="utf-8")
    print(f"Wrote {output}")

def main(argv):
    if len(argv) < 2:
        print("usage: mk_report.py <RUN_DIR>")
        return 2
    write_report(Path(argv[1]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

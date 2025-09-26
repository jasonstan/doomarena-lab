#!/usr/bin/env python3
from __future__ import annotations
import json, csv, html, sys
from pathlib import Path
from typing import Iterable

# Usage: python tools/mk_report.py RESULTS_DIR
# Writes: <RESULTS_DIR>/index.html (always)

def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def _read_rows_jsonl(p: Path, limit: int = 25):
    rows = []
    try:
        with p.open("r", encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
                if i + 1 >= limit:
                    break
    except Exception:
        pass
    return rows

def _read_summary_csv(p: Path):
    try:
        with p.open("r", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    except Exception:
        return []

def _h(s: str) -> str:
    return html.escape(s, quote=True)

def _mk_trial_table(rows: Iterable[dict]) -> str:
    if not rows:
        return "<p><em>No per-trial rows available.</em></p>"
    # Try common keys; fall back to first two stringy fields
    cols = ["attack_id", "attack_prompt", "input", "output", "judge", "pass"]
    present = [c for c in cols if any(c in r for r in rows)]
    if not present:
        # choose up to 4 columns that look stringy
        first = rows[0]
        present = [k for k, v in first.items() if isinstance(v, (str, int, float))][:4]
    thead = "".join(f"<th>{_h(c)}</th>" for c in present)
    trs = []
    for r in rows:
        tds = "".join(f"<td>{_h(str(r.get(c, '')))}</td>" for c in present)
        trs.append(f"<tr>{tds}</tr>")
    return f"""
<table border="1" cellspacing="0" cellpadding="6">
  <thead><tr>{thead}</tr></thead>
  <tbody>
    {''.join(trs)}
  </tbody>
</table>
"""

def main():
    if len(sys.argv) != 2:
        print("usage: mk_report.py RESULTS_DIR", file=sys.stderr)
        sys.exit(2)

    run_dir = Path(sys.argv[1])
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / "index.html"

    # Inputs we try to use if present
    run_json = _read_json(run_dir / "run.json")
    rows = _read_rows_jsonl(run_dir / "rows.jsonl", limit=25)
    summary_rows = _read_summary_csv(run_dir / "summary.csv")

    # Pull friendly metadata if available
    model = (run_json or {}).get("model") or (run_json or {}).get("config", {}).get("model") or ""
    seed = (run_json or {}).get("seed")
    trials = (run_json or {}).get("trials")
    asr = ""
    if summary_rows:
        # look for common columns
        r0 = summary_rows[0]
        asr = r0.get("asr") or r0.get("pass_rate") or ""

    # Build the page
    badges = []
    if model: badges.append(f"<span>model: <code>{_h(model)}</code></span>")
    if seed is not None: badges.append(f"<span>seed: <code>{_h(str(seed))}</code></span>")
    if trials is not None: badges.append(f"<span>trials: <code>{_h(str(trials))}</code></span>")
    if asr: badges.append(f"<span>ASR: <code>{_h(str(asr))}</code></span>")
    badges_html = " · ".join(badges) if badges else "<em>No run metadata found.</em>"

    trial_table = _mk_trial_table(rows)

    # Link out to artifacts if present
    links = []
    for name in ("summary.csv", "summary.svg", "run.json", "rows.jsonl"):
        p = run_dir / name
        if p.exists():
            links.append(f'<li><a href="{_h(name)}">{_h(name)}</a></li>')
    links_html = "<ul>" + "".join(links) + "</ul>" if links else "<p><em>No artifacts found.</em></p>"

    html_doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>DoomArena-Lab Report — { _h(run_dir.name) }</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; line-height: 1.4; padding: 24px; }}
    h1 {{ margin: 0 0 8px; }}
    .badges span {{ background: #f3f4f6; border-radius: 6px; padding: 4px 8px; margin-right: 6px; display: inline-block; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
    th, td {{ text-align: left; vertical-align: top; }}
    code {{ background: #f8fafc; padding: 0 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>DoomArena-Lab Report</h1>
  <p>Run: <code>{_h(run_dir.name)}</code></p>
  <p class="badges">{badges_html}</p>

  <h2>Trial I/O (first {len(rows)} rows)</h2>
  {trial_table}

  <h2>Artifacts</h2>
  {links_html}
</body>
</html>
"""
    out.write_text(html_doc, encoding="utf-8")

if __name__ == "__main__":
    main()

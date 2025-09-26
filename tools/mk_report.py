from pathlib import Path
import sys, json, csv

def load_summary(run_dir: Path):
    p_json = run_dir / "summary_index.json"
    if p_json.exists():
        try:
            return "json", json.loads(p_json.read_text(encoding="utf-8"))
        except Exception:
            pass
    p_csv = run_dir / "summary.csv"
    if p_csv.exists():
        try:
            rows = list(csv.DictReader(p_csv.open(encoding="utf-8")))
            return "csv", {"csv_rows": rows}
        except Exception:
            pass
    return "none", {}

def _degraded_html(run_dir: Path, err: Exception | None = None) -> str:
    msg = f"{type(err).__name__}: {err}" if err else "no data"
    return f"""<!doctype html><meta charset="utf-8">
<title>DoomArena-Lab Report (degraded)</title>
<h1>Report (degraded)</h1>
<p>Could not render full report ({msg}).</p>
<p>Artifacts are in <code>{run_dir.name}</code>.</p>
<ul>
  <li><code>summary.csv</code></li>
  <li><code>summary.svg</code></li>
  <li><code>rows.jsonl</code></li>
  <li><code>run.json</code></li>
</ul>
"""

def main():
    run_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    if not run_dir or not run_dir.exists():
        print("ERROR: mk_report: missing run_dir", file=sys.stderr)
        sys.exit(2)
    out_path = run_dir / "index.html"

    mode, data = load_summary(run_dir)

    try:
        from tools.report.html_report import render_html  # type: ignore
    except Exception as e:
        out_path.write_text(_degraded_html(run_dir, e), encoding="utf-8")
        print(f"Wrote {out_path} (degraded: import error)")
        return

    try:
        html = render_html(run_dir, data, mode=mode)
    except Exception as e:
        html = _degraded_html(run_dir, e)

    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()

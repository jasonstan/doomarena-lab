# tools/mk_report.py
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


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


def write_report(run_dir: Path) -> None:
    run_dir = resolve_run_dir(run_dir)
    out_path = run_dir / "index.html"

    mode, data = load_summary(run_dir)

    try:
        from tools.report.html_report import render_html  # type: ignore[attr-defined]
    except Exception as import_error:
        html = _degraded_html(run_dir, import_error)
        out_path.write_text(html, encoding="utf-8")
        print(f"Wrote {out_path} (degraded: import error)")
        return

    degraded = False
    try:
        html = render_html(run_dir, data, mode=mode)
    except Exception as err:
        html = _degraded_html(run_dir, err)
        degraded = True

    out_path.write_text(html, encoding="utf-8")
    if degraded:
        print(f"Wrote {out_path} (degraded)")
    else:
        print(f"Wrote {out_path}")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv if argv is None else argv
    if len(args) < 2:
        print("ERROR: mk_report: missing run_dir", file=sys.stderr)
        return 2

    requested = Path(args[1])
    run_dir = resolve_run_dir(requested)
    if not run_dir.exists():
        print(f"ERROR: mk_report: run_dir does not exist: {requested}", file=sys.stderr)
        return 2

    write_report(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

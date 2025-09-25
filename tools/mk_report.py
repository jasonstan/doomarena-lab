from __future__ import annotations

import csv
import html
import json
import sys
from pathlib import Path

from tools.report.html_report import render_html


def resolve_run_dir(path: Path) -> Path:
    """Resolve symlinks and pointer files under ``results/``."""

    resolved = path.resolve(strict=False)
    if resolved.exists():
        return resolved

    pointer = path.parent / f"{path.name}.path"
    if pointer.exists():
        target_text = pointer.read_text(encoding="utf-8").strip()
        if target_text:
            target = Path(target_text)
            if target.exists():
                try:
                    return target.resolve()
                except Exception:
                    return target
    return resolved


def load_summary(run_dir: Path) -> tuple[str, dict[str, object]]:
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


def write_report(run_dir: Path) -> Path:
    run_dir = resolve_run_dir(run_dir)
    if not run_dir.exists():
        raise FileNotFoundError(f"run_dir does not exist: {run_dir}")

    mode, data = load_summary(run_dir)
    try:
        html_output = render_html(run_dir, data, mode=mode)
    except Exception as exc:  # pragma: no cover - defensive fallback
        message = html.escape(str(exc))
        html_output = (
            "<!doctype html><meta charset=\"utf-8\">"
            "<title>DoomArena-Lab Report (degraded)</title>"
            "<h1>Report (degraded)</h1>"
            f"<p>Could not render full report: {type(exc).__name__}: {message}</p>"
            f"<p>Artifacts present in <code>{html.escape(run_dir.name or str(run_dir))}</code>.</p>"
        )

    out_path = run_dir / "index.html"
    out_path.write_text(html_output, encoding="utf-8")
    return out_path


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("ERROR: mk_report: missing run_dir", file=sys.stderr)
        return 2

    run_dir = resolve_run_dir(Path(args[0]))
    if not run_dir.exists():
        print("ERROR: mk_report: missing run_dir", file=sys.stderr)
        return 2

    out_path = write_report(run_dir)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

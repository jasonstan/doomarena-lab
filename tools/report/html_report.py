"""HTML report wrapper that prefers ``summary_index.json`` with a CSV fallback."""

from __future__ import annotations

import argparse
import csv, json, os
import sys
from pathlib import Path
from typing import Any, Mapping

from tools import mk_report


def load_summary_index(run_dir: str):
    p = os.path.join(run_dir, "summary_index.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Fallback from summary.csv (best-effort, no new deps)
        csv_path = os.path.join(run_dir, "summary.csv")
        totals = callable_cnt = pass_cnt = fail_cnt = 0
        pre_counts, post_counts = {}, {}
        if os.path.isfile(csv_path):
            with open(csv_path, newline="", encoding="utf-8") as f:
                r = csv.DictReader(f)
                for row in r:
                    totals += 1
                    if (row.get("callable") or "").lower() == "true":
                        callable_cnt += 1
                        if (row.get("success") or "").lower() == "true":
                            pass_cnt += 1
                        else:
                            fail_cnt += 1
                    pre = row.get("pre_reason_code") or ""
                    post = row.get("post_reason_code") or ""
                    if pre: pre_counts[pre] = pre_counts.get(pre, 0) + 1
                    if post: post_counts[post] = post_counts.get(post, 0) + 1
        top_pre = sorted(pre_counts.items(), key=lambda x: (-x[1], x[0]))[:10]
        top_post = sorted(post_counts.items(), key=lambda x: (-x[1], x[0]))[:10]
        return {
            "totals": {"rows": totals, "callable": callable_cnt, "passes": pass_cnt, "fails": fail_cnt},
            "callable_pass_rate": (pass_cnt / callable_cnt) if callable_cnt else 0.0,
            "top_reasons": {"pre": top_pre, "post": top_post},
            "malformed": 0,
        }


def write_html_report(
    run_dir: Path, *, summary_index: Mapping[str, Any] | None = None
) -> Path:
    resolved_dir = mk_report.resolve_run_dir(run_dir)
    run_dir_path = Path(os.fspath(resolved_dir))
    if summary_index is None:
        summary_index = load_summary_index(os.fspath(run_dir_path))
    else:
        summary_index = dict(summary_index)
    mk_report.write_report(run_dir_path)
    return run_dir_path / "index.html"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate DoomArena HTML report")
    parser.add_argument("run_dir", help="Run directory to render")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    write_html_report(Path(args.run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

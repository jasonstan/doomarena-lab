"""HTML report wrapper that prefers ``summary_index.json`` with a CSV fallback."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

from tools import mk_report


def _as_int(value: object) -> int | None:
    """Best-effort conversion to ``int`` returning ``None`` on failure."""

    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return None


def _csv_truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"true", "1", "yes", "y", "on"}


def _order_reasons(counts: Mapping[str, int]) -> list[list[Any]]:
    items: list[list[Any]] = []
    for key, value in counts.items():
        key_text = str(key).strip()
        if not key_text:
            continue
        count = _as_int(value)
        if count is None or count <= 0:
            continue
        items.append([key_text, count])
    items.sort(key=lambda pair: (-pair[1], pair[0]))
    return items


def _load_summary_index_file(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "summary_index.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        return data
    return None


def _summary_index_from_csv(run_dir: Path) -> dict[str, Any] | None:
    csv_path = run_dir / "summary.csv"
    if not csv_path.exists():
        return None

    try:
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            totals = 0
            callable_cnt = 0
            pass_cnt = 0
            fail_cnt = 0
            top_pre: dict[str, int] = {}
            top_post: dict[str, int] = {}
            for row in reader:
                totals += 1
                callable_value = row.get("callable") or row.get("called_trials")
                success_value = row.get("success") or row.get("passed_trials")

                callable_num = _as_int(callable_value)
                success_num = _as_int(success_value)
                if callable_num is not None:
                    c_total = max(callable_num, 0)
                    callable_cnt += c_total
                    if success_num is not None:
                        s_total = max(min(success_num, c_total), 0)
                    elif _csv_truthy(success_value):
                        s_total = c_total
                    else:
                        s_total = 0
                    pass_cnt += s_total
                    fail_cnt += max(c_total - s_total, 0)
                elif _csv_truthy(callable_value):
                    callable_cnt += 1
                    if success_num is not None:
                        s_total = 1 if success_num > 0 else 0
                    elif _csv_truthy(success_value):
                        s_total = 1
                    else:
                        s_total = 0
                    pass_cnt += s_total
                    fail_cnt += 1 - s_total

                pre_reason = (
                    row.get("pre_reason_code")
                    or row.get("pre_reason")
                    or row.get("pre_reason_text")
                    or ""
                )
                pre_reason = str(pre_reason).strip()
                if pre_reason:
                    top_pre[pre_reason] = top_pre.get(pre_reason, 0) + 1

                post_reason = (
                    row.get("post_reason_code")
                    or row.get("post_reason")
                    or row.get("post_reason_text")
                    or ""
                )
                post_reason = str(post_reason).strip()
                if post_reason:
                    top_post[post_reason] = top_post.get(post_reason, 0) + 1

    except (OSError, csv.Error):
        return None

    pass_rate = pass_cnt / float(callable_cnt) if callable_cnt else 0.0

    return {
        "totals": {
            "rows": totals,
            "callable": callable_cnt,
            "passes": pass_cnt,
            "fails": max(fail_cnt, 0),
        },
        "callable_pass_rate": pass_rate,
        "top_reasons": {
            "pre": _order_reasons(top_pre),
            "post": _order_reasons(top_post),
        },
        "malformed": 0,
    }


def load_summary_index(
    run_dir: Path, summary_index: Mapping[str, Any] | None = None
) -> tuple[dict[str, Any], bool]:
    if summary_index is not None:
        return dict(summary_index), False

    resolved = Path(os.fspath(run_dir))

    file_payload = _load_summary_index_file(resolved)
    if file_payload is not None:
        return file_payload, False

    csv_payload = _summary_index_from_csv(resolved)
    if csv_payload is not None:
        return csv_payload, True

    empty_payload: dict[str, Any] = {
        "totals": {"rows": 0, "callable": 0, "passes": 0, "fails": 0},
        "callable_pass_rate": 0.0,
        "top_reasons": {"pre": [], "post": []},
        "malformed": 0,
    }
    return empty_payload, True


def write_html_report(
    run_dir: Path, *, summary_index: Mapping[str, Any] | None = None
) -> Path:
    """Generate the HTML report for ``run_dir``.

    ``summary_index`` is optional and, when omitted, the function will read the
    JSON payload from disk, falling back to ``summary.csv`` when necessary.
    """

    resolved_dir = mk_report.resolve_run_dir(run_dir)
    _payload, used_fallback = load_summary_index(resolved_dir, summary_index)
    if used_fallback:
        print(
            f"NOTE: summary_index.json missing for {resolved_dir}; using fallback data.",
            file=sys.stderr,
        )
    # The mk_report module handles rendering; we only ensure prerequisites exist.
    mk_report.write_report(resolved_dir)
    return resolved_dir / "index.html"


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

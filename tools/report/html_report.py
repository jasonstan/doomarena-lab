"""HTML report wrapper that prefers ``summary_index.json`` with a CSV fallback."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from tools import mk_report


def _to_int(value: object) -> int:
    """Best-effort conversion to ``int`` (fallback to ``0``)."""

    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    text = str(value).strip()
    if not text:
        return 0
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return 0


def _order_reasons(counts: Mapping[str, Any]) -> list[list[Any]]:
    items: list[list[Any]] = []
    for key, value in counts.items():
        key_text = str(key).strip()
        if not key_text:
            continue
        count = _to_int(value)
        if count <= 0:
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
            rows = list(reader)
    except (OSError, csv.Error):
        return None
    if not rows:
        return None

    callable_total = 0
    passed_total = 0
    pre_counts: MutableMapping[str, int] = {}
    post_counts: MutableMapping[str, int] = {}
    for row in rows:
        callable_total += _to_int(row.get("callable") or row.get("called_trials"))
        passed_total += _to_int(row.get("success") or row.get("passed_trials"))
        pre_reason = str(row.get("pre_reason") or "").strip()
        if pre_reason:
            pre_counts[pre_reason] = pre_counts.get(pre_reason, 0) + 1
        post_reason = str(row.get("post_reason") or "").strip()
        if post_reason:
            post_counts[post_reason] = post_counts.get(post_reason, 0) + 1

    fails_total = callable_total - passed_total
    if fails_total < 0:
        fails_total = 0
    pass_rate = passed_total / float(callable_total) if callable_total else 0.0

    return {
        "totals": {
            "rows": len(rows),
            "callable": callable_total,
            "passes": passed_total,
            "fails": fails_total,
        },
        "callable_pass_rate": pass_rate,
        "top_reasons": {
            "pre": _order_reasons(pre_counts),
            "post": _order_reasons(post_counts),
        },
        "malformed": 0,
    }


def _ensure_summary_index(
    run_dir: Path, summary_index: Mapping[str, Any] | None
) -> tuple[dict[str, Any], bool]:
    if summary_index is not None:
        return dict(summary_index), False

    file_payload = _load_summary_index_file(run_dir)
    if file_payload is not None:
        return file_payload, False

    csv_payload = _summary_index_from_csv(run_dir)
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
    _payload, used_fallback = _ensure_summary_index(resolved_dir, summary_index)
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

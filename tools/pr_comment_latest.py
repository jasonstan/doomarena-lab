#!/usr/bin/env python3
"""Build PR comment markdown summarizing the latest smoke results."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def read_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [{k or "": v or "" for k, v in row.items()} for row in reader]


def rows_to_markdown(rows: list[dict[str, str]], limit: int = 10) -> str:
    if not rows:
        return "_No rows in `summary.csv`_"
    headers = list(rows[0].keys())
    lines = []
    header_row = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    lines.append(header_row)
    lines.append(separator)
    for row in rows[:limit]:
        line = "| " + " | ".join(str(row.get(h, "")) for h in headers) + " |"
        lines.append(line)
    remaining = len(rows) - limit
    if remaining > 0:
        extras = ["…"] * len(headers)
        if len(headers) > 1:
            extras[1] = f"({remaining} more rows)"
        extras_line = "| " + " | ".join(extras) + " |"
        lines.append(extras_line)
    return "\n".join(lines)


def load_schema(results_dir: Path) -> str:
    run_json = results_dir / "run.json"
    if not run_json.exists():
        return ""
    try:
        data = json.loads(run_json.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return str(data.get("summary_schema", ""))


def main(argv: list[str]) -> int:
    results = Path(argv[1]) if len(argv) > 1 else Path("results/LATEST")
    rows = read_rows(results / "summary.csv")
    md_table = rows_to_markdown(rows)
    schema = load_schema(results)

    lines = [
        "### DoomArena-Lab PR smoke results",
        "",
        f"Schema: `{schema or 'n/a'}`",
        "",
        "**Latest artifacts**: `results/LATEST/` (CSV/SVG/HTML)",
        "",
        md_table,
        "",
        "_Open_ `results/LATEST/index.html` and `summary.svg` from **Artifacts** in this run.",
    ]
    body = "\n".join(lines).strip()

    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

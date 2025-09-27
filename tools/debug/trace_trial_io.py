#!/usr/bin/env python3
"""Inspect callable trial rows to verify prompt/response persistence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:  # pragma: no cover - script executed from repo root
    from tools.report_utils import (
        EMPTY_SENTINEL,
        ResolvedField,
        resolve_prompt_field,
        resolve_response_field,
    )
except ModuleNotFoundError:  # pragma: no cover - script executed from tools/
    from report_utils import (  # type: ignore
        EMPTY_SENTINEL,
        ResolvedField,
        resolve_prompt_field,
        resolve_response_field,
    )

PLACEHOLDER_VALUES = {"", "—", EMPTY_SENTINEL}


def _is_placeholder(text: str) -> bool:
    stripped = text.strip()
    return stripped in PLACEHOLDER_VALUES


def _iter_rows(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"[warn] failed to parse line {line_no}: {exc}", file=sys.stderr)


def _format_preview(text: str, limit: int = 120) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _resolve_fields(row: dict[str, Any]) -> tuple[ResolvedField, ResolvedField]:
    prompt_res = resolve_prompt_field(row)
    response_res = resolve_response_field(row)
    return prompt_res, response_res


def trace_rows(rows_path: Path, limit: int) -> int:
    printed = 0
    placeholder_both = 0

    for row in _iter_rows(rows_path):
        if row.get("callable") is not True:
            continue
        prompt_res, response_res = _resolve_fields(row)
        prompt_text = prompt_res.text or ""
        response_text = response_res.text or ""

        prompt_placeholder = _is_placeholder(prompt_text)
        response_placeholder = _is_placeholder(response_text)
        if prompt_placeholder and response_placeholder:
            placeholder_both += 1

        print(
            f"trial={row.get('trial_id', '—')} attack={row.get('attack_id', '—')} success={row.get('success')}"
        )
        print(
            f"  prompt[{prompt_res.source}]: {_format_preview(prompt_text)}"
        )
        print(
            f"  response[{response_res.source}]: {_format_preview(response_text)}"
        )
        print("---")

        printed += 1
        if printed >= limit:
            break

    if printed == 0:
        print("No callable rows found.")
        return 2

    if placeholder_both / printed > 0.8:
        return 1
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows_path", type=Path, help="Path to rows.jsonl file")
    parser.add_argument("--k", type=int, default=10, help="Callable rows to inspect (default: 10)")
    args = parser.parse_args(argv[1:])

    if args.k <= 0:
        parser.error("--k must be a positive integer")

    if not args.rows_path.exists():
        parser.error(f"rows file not found: {args.rows_path}")

    return trace_rows(args.rows_path, args.k)


if __name__ == "__main__":
    sys.exit(main(sys.argv))

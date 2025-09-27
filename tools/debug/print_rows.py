#!/usr/bin/env python3
"""Inspect ``rows.jsonl`` and surface prompt/response candidates per row."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from tools.report_utils import get_prompt, get_response
except ModuleNotFoundError:  # pragma: no cover - allow running from tools/
    from report_utils import get_prompt, get_response  # type: ignore

PROMPT_KEYS: tuple[tuple[str, str | None], ...] = (
    ("input_text", None),
    ("input_case", "prompt"),
    ("input", "prompt"),
    ("attack_prompt", None),
    ("prompt", None),
)

RESPONSE_KEYS: tuple[tuple[str, str | None], ...] = (
    ("output_text", None),
    ("model_response", None),
    ("response", "text"),
    ("response", None),
    ("output", None),
    ("model_output", None),
)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _resolve(row: Mapping[str, Any], keys: Iterable[tuple[str, str | None]]) -> tuple[str, str]:
    for outer, inner in keys:
        value = row.get(outer)
        if inner is None:
            if value not in (None, "", "—"):
                return outer, _stringify(value)
            continue
        if isinstance(value, Mapping):
            candidate = value.get(inner)
            if candidate not in (None, "", "—"):
                return f"{outer}.{inner}", _stringify(candidate)
    return "", ""


def _shorten(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def inspect_rows(path: Path, *, limit: int = 10) -> None:
    shown = 0
    with path.open("r", encoding="utf-8") as handle:
        for idx, raw in enumerate(handle):
            if shown >= limit:
                break
            raw = raw.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                print(f"[row {idx}] !! malformed JSON")
                continue
            if payload.get("callable") is not True:
                continue
            prompt_key, prompt_value = _resolve(payload, PROMPT_KEYS)
            response_key, response_value = _resolve(payload, RESPONSE_KEYS)
            print(f"[row {idx}] trial_id={payload.get('trial_id', '?')} attack_id={payload.get('attack_id', '?')}")
            print(f"  prompt key: {prompt_key or '—'}")
            print(f"  prompt val: {_shorten(prompt_value) or '—'}")
            print(f"  fallback prompt: {_shorten(get_prompt(payload)) or '—'}")
            print(f"  response key: {response_key or '—'}")
            print(f"  response val: {_shorten(response_value) or '—'}")
            print(f"  fallback response: {_shorten(get_response(payload)) or '—'}")
            shown += 1
    if shown == 0:
        print("No callable rows found in", path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=Path, help="Path to rows.jsonl")
    parser.add_argument("--limit", type=int, default=10, help="Maximum callable rows to display")
    args = parser.parse_args()
    inspect_rows(args.rows, limit=max(1, args.limit))


if __name__ == "__main__":  # pragma: no cover - manual inspection utility
    main()

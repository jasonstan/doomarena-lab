"""Simple guardrail helpers for REAL experiments."""

from __future__ import annotations

import re


_AMOUNT_PATTERN = re.compile(r"\$?(\d{1,5})")


def _extract_amount(text: str | None) -> int | None:
    if not text:
        return None
    match = _AMOUNT_PATTERN.search(text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def pre_call_guard(user_text: str | None) -> str:
    amount = _extract_amount((user_text or "").lower())
    if amount is not None and amount > 200:
        return "deny"
    if amount is not None and amount > 100:
        return "warn"
    return "allow"


def post_call_guard(model_output: str | None) -> str:
    output = (model_output or "").lower()
    amount = _extract_amount(output)
    if amount is not None and amount > 200:
        return "deny"
    if amount is not None and amount > 100 and ("manager" not in output and "approval" not in output):
        return "warn"
    return "allow"

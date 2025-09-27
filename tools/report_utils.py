"""Utility helpers for building HTML report content."""
from __future__ import annotations

from html import escape
from typing import Any, Iterable, Mapping, Sequence


KEY_CANDIDATES_PROMPT = [
    ("input_case", "prompt"),
    ("input", "prompt"),
    ("attack_prompt", None),
    ("prompt", None),
    ("request", None),
]


KEY_CANDIDATES_RESPONSE = [
    ("model_response", None),
    ("response", "text"),
    ("response", None),
    ("output", None),
    ("model_output", None),
]


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, Mapping):
        for key in ("text", "content", "message", "value"):
            if key in value:
                return _stringify(value.get(key))
        choices = value.get("choices")
        if isinstance(choices, Sequence) and not isinstance(
            choices, (str, bytes, bytearray)
        ):
            parts = []
            for item in choices:
                text = _stringify(item)
                if text:
                    parts.append(text)
            return "\n".join(parts)
        return ""
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        pieces = [_stringify(item) for item in value]
        return "\n".join(piece for piece in pieces if piece)
    return str(value)


def pick_field(row: Mapping[str, Any], candidates: Iterable[Sequence[str | None]]) -> str:
    for path in candidates:
        if not path:
            continue
        current: Any = row
        for key in path:
            if key is None:
                continue
            if not isinstance(current, Mapping):
                current = None
                break
            current = current.get(key)
        if current is None:
            continue
        text = _stringify(current)
        if text and text.strip():
            return text
    return ""


def get_prompt(row: Mapping[str, Any]) -> str:
    return pick_field(row, KEY_CANDIDATES_PROMPT)


def get_response(row: Mapping[str, Any]) -> str:
    return pick_field(row, KEY_CANDIDATES_RESPONSE)


def truncate_for_preview(text: str, limit: int = 240) -> str:
    if text is None:
        return ""
    if limit <= 0:
        return ""
    clean = str(text)
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "…"


def expandable_block(block_id: str, full_text: str, limit: int = 240) -> str:
    full = full_text or ""
    preview = truncate_for_preview(full, limit=limit)
    safe_id = escape(str(block_id), quote=True)
    preview_html = escape(preview, quote=False)
    full_html = escape(full, quote=False)
    return (
        '<div class="expander">'
        f'<div class="preview">{preview_html}</div>'
        f'<button type="button" class="toggle" data-expands="{safe_id}">Expand</button>'
        f'<div class="fulltext" id="{safe_id}">{full_html}</div>'
        "</div>"
    )


def safe_get(mapping: Mapping[str, Any] | None, key: str, default: str = "—") -> str:
    """Return a printable string for ``mapping[key]`` or ``default``.

    ``None`` values, missing keys, and empty strings collapse to the default
    placeholder to keep table rendering consistent.
    """

    if not isinstance(mapping, Mapping):
        return default
    value = mapping.get(key, default)
    if value in (None, ""):
        return default
    return str(value)

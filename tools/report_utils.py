"""Utility helpers for building HTML report content."""
from __future__ import annotations

import html
from typing import Mapping, Any


def truncate_for_preview(text: str, limit: int = 240) -> str:
    """Return a shortened preview string limited to ``limit`` characters.

    The preview keeps whitespace intact and appends an ellipsis when the
    original text exceeds the limit.
    """

    if text is None:
        return ""
    if limit <= 0:
        return ""
    clean = str(text)
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "…"


def expandable_block(block_id: str, preview: str, full: str) -> str:
    """Return an HTML block with a preview, toggle button, and full text."""

    safe_id = html.escape(block_id, quote=True)
    preview_html = html.escape(preview or "", quote=False)
    full_html = html.escape(full or "", quote=False)
    return (
        f"<div class=\"expander\">"
        f"<div class=\"preview\">{preview_html}</div>"
        f"<button type=\"button\" class=\"toggle\" data-expands=\"{safe_id}\">Expand</button>"
        f"<div class=\"fulltext\" id=\"{safe_id}\">{full_html}</div>"
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

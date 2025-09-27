"""Utility helpers for building HTML report content."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Iterable as IterableType, Sequence as SequenceType


EMPTY_SENTINEL = "[EMPTY]"


PROMPT_KEY_CANDIDATES: list[tuple[str, ...]] = [
    ("input_text",),
    ("input_case", "prompt"),
    ("input", "prompt"),
    ("input", "attack_prompt"),
    ("attack_prompt",),
    ("prompt",),
    ("request", "prompt"),
    ("request", "attack_prompt"),
    ("request", "input", "prompt"),
    ("request", "input", "attack_prompt"),
    ("request", "input_text"),
    ("input",),
    ("raw_input",),
]


RESPONSE_KEY_CANDIDATES: list[tuple[str, ...]] = [
    ("output_text",),
    ("model_response",),
    ("response", "text"),
    ("response", "output_text"),
    ("response", "content"),
    ("response", "choices"),
    ("response",),
    ("completion", "text"),
    ("completion", "choices"),
    ("completion",),
    ("output", "text"),
    ("output", "content"),
    ("output",),
    ("model_output",),
    ("raw_output",),
]


PROMPT_MESSAGE_PATHS = [
    ("messages",),
    ("input", "messages"),
    ("request", "messages"),
    ("request", "input", "messages"),
]


RESPONSE_MESSAGE_PATHS = [
    ("response", "messages"),
    ("output", "messages"),
    ("completion", "messages"),
]


PROMPT_FALLBACK_KEYS = ("input", "input_text")


RESPONSE_FALLBACK_KEYS = (
    "raw_output",
    "output_text",
    "output",
    "response",
    "completion",
    "model_output",
    "model_response",
)


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


@dataclass
class ResolvedField:
    text: str
    source: str


def _resolve_from_candidates(
    row: Mapping[str, Any],
    candidates: IterableType[SequenceType[str]],
) -> ResolvedField | None:
    for path in candidates:
        if not path:
            continue
        current: Any = row
        valid = True
        for key in path:
            if not isinstance(current, Mapping):
                valid = False
                break
            current = current.get(key)
        if not valid or current is None:
            continue
        text = _stringify(current)
        if text:
            return ResolvedField(text=text, source=".".join(path))
        if text == "":
            # keep searching – fallbacks may yield a literal string
            continue
    return None


def _resolve_from_messages(
    row: Mapping[str, Any],
    paths: IterableType[SequenceType[str]],
    *,
    roles: set[str],
) -> ResolvedField | None:
    for path in paths:
        value = _dig(row, path)
        text = _join_messages(value, roles=roles)
        if text:
            path_label = ".".join(path) if path else "messages"
            return ResolvedField(text=text, source=f"{path_label}[*]")
    return None


def _resolve_from_fallbacks(
    row: Mapping[str, Any],
    keys: IterableType[str],
) -> ResolvedField | None:
    for key in keys:
        text = _stringify(row.get(key))
        if text:
            return ResolvedField(text=text, source=key)
    return None


def resolve_prompt_field(row: Mapping[str, Any]) -> ResolvedField:
    direct = _resolve_from_candidates(row, PROMPT_KEY_CANDIDATES)
    if direct:
        return direct

    message_based = _resolve_from_messages(row, PROMPT_MESSAGE_PATHS, roles={"user"})
    if message_based:
        return message_based

    fallback = _resolve_from_fallbacks(row, PROMPT_FALLBACK_KEYS)
    if fallback:
        return fallback

    return ResolvedField(text="—", source="∅")


def resolve_response_field(row: Mapping[str, Any]) -> ResolvedField:
    direct = _resolve_from_candidates(row, RESPONSE_KEY_CANDIDATES)
    if direct:
        return direct

    message_based = _resolve_from_messages(row, RESPONSE_MESSAGE_PATHS, roles={"assistant"})
    if message_based:
        return message_based

    fallback = _resolve_from_fallbacks(row, RESPONSE_FALLBACK_KEYS)
    if fallback:
        return fallback

    return ResolvedField(text="—", source="∅")


def get_prompt(row: Mapping[str, Any]) -> str:
    return resolve_prompt_field(row).text


def get_response(row: Mapping[str, Any]) -> str:
    return resolve_response_field(row).text


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


def _dig(mapping: Mapping[str, Any], path: Sequence[str]) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _join_messages(value: Any, roles: set[str] | None = None) -> str:
    if isinstance(value, Mapping):
        # Some schemas wrap the messages in an object with its own keys.
        if "messages" in value:
            value = value.get("messages")

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ""

    parts: list[str] = []
    for message in value:
        if not isinstance(message, Mapping):
            text = _stringify(message)
            if text and text.strip():
                parts.append(text)
            continue

        role = message.get("role")
        if roles and role and str(role).lower() not in roles:
            continue

        text = _stringify(message.get("content"))
        if not text:
            text = _stringify(message.get("text"))
        if not text:
            text = _stringify(message.get("message"))
        if not text:
            text = _stringify(message.get("value"))
        if not text:
            text = _stringify(message)
        if text and text.strip():
            parts.append(text)

    return "\n\n".join(parts)

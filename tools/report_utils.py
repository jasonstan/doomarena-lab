"""Utility helpers for building HTML report content."""
from __future__ import annotations

from html import escape
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Iterable as TypingIterable

try:  # pragma: no cover - script invoked from tools/
    from tools.constants import (
        EMPTY_PLACEHOLDER,
        MISSING_INPUT_PLACEHOLDER,
        MISSING_OUTPUT_PLACEHOLDER,
        PLACEHOLDER_INPUT_VALUES,
        PLACEHOLDER_OUTPUT_VALUES,
    )
except ModuleNotFoundError:  # pragma: no cover - fallback when executed from tools/
    from constants import (  # type: ignore
        EMPTY_PLACEHOLDER,
        MISSING_INPUT_PLACEHOLDER,
        MISSING_OUTPUT_PLACEHOLDER,
        PLACEHOLDER_INPUT_VALUES,
        PLACEHOLDER_OUTPUT_VALUES,
    )


KEY_CANDIDATES_PROMPT = [
    ("input_case", "prompt"),
    ("input", "prompt"),
    ("input", "attack_prompt"),
    ("attack_prompt", None),
    ("prompt", None),
    ("request", "prompt"),
    ("request", "attack_prompt"),
    ("request", "input", "prompt"),
    ("request", "input", "attack_prompt"),
    ("request", None),
    ("input_text", None),
    ("request", "input_text"),
    ("raw_input", None),
]


KEY_CANDIDATES_RESPONSE = [
    ("model_response", None),
    ("response", "text"),
    ("response", "output_text"),
    ("response", "content"),
    ("response", "choices"),
    ("response", None),
    ("completion", "text"),
    ("completion", "choices"),
    ("completion", None),
    ("output", "text"),
    ("output", "content"),
    ("output", None),
    ("output_text", None),
    ("model_output", None),
    ("raw_output", None),
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
    text = pick_field(row, KEY_CANDIDATES_PROMPT)
    if text:
        return text

    for path in PROMPT_MESSAGE_PATHS:
        value = _dig(row, path)
        text = _join_messages(value, roles={"user"})
        if text:
            return text

    for key in PROMPT_FALLBACK_KEYS:
        text = _stringify(row.get(key))
        if text and text.strip():
            return text

    return ""


def get_response(row: Mapping[str, Any]) -> str:
    text = pick_field(row, KEY_CANDIDATES_RESPONSE)
    if text:
        return text

    for path in RESPONSE_MESSAGE_PATHS:
        value = _dig(row, path)
        text = _join_messages(value, roles={"assistant"})
        if text:
            return text

    for key in RESPONSE_FALLBACK_KEYS:
        text = _stringify(row.get(key))
        if text and text.strip():
            return text

    return ""


def truncate_for_preview(text: str, limit: int = 240) -> str:
    if text is None:
        return ""
    if limit <= 0:
        return ""
    clean = str(text)
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "…"


def expandable_block(
    block_id: str,
    full_text: str,
    limit: int = 240,
    *,
    classes: TypingIterable[str] | None = None,
) -> str:
    full = full_text or ""
    preview = truncate_for_preview(full, limit=limit)
    safe_id = escape(str(block_id), quote=True)
    preview_html = escape(preview, quote=False)
    full_html = escape(full, quote=False)
    class_tokens = ["expander"]
    if classes:
        class_tokens.extend(str(token) for token in classes if token)
    class_attr = " ".join(dict.fromkeys(class_tokens))
    return (
        f'<div class="{class_attr}">'
        f'<div class="preview">{preview_html}</div>'
        f'<button type="button" class="toggle" data-expands="{safe_id}">Expand</button>'
        f'<div class="fulltext" id="{safe_id}">{full_html}</div>'
        "</div>"
    )


def normalize_literal(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def coalesce_literal(
    primary: Any,
    fallback: str,
    *,
    missing_placeholder: str,
    placeholder_values: TypingIterable[str] | None = None,
) -> tuple[str, bool]:
    text = normalize_literal(primary)
    if text:
        if placeholder_values is None:
            if missing_placeholder == MISSING_INPUT_PLACEHOLDER:
                placeholder_set = set(PLACEHOLDER_INPUT_VALUES)
            elif missing_placeholder == MISSING_OUTPUT_PLACEHOLDER:
                placeholder_set = set(PLACEHOLDER_OUTPUT_VALUES)
            else:
                placeholder_set = {EMPTY_PLACEHOLDER}
        else:
            placeholder_set = set(placeholder_values)
        return text, text in placeholder_set
    if fallback:
        return fallback, False
    return missing_placeholder, True


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

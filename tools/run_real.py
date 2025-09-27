"""Utilities for executing REAL runs and streaming per-attempt rows."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

CaseLike = Mapping[str, Any]


EMPTY_SENTINEL = "[EMPTY]"


def _debug_enabled() -> bool:
    return os.getenv("DEBUG_TRIAL_IO", "0") == "1"


_DEBUG_EMITTED_COUNT = 0


def _log_debug_snapshot(
    rows_file: Path,
    *,
    trial_id: Any,
    attack_id: Any,
    callable_flag: bool,
    success_flag: Any,
    input_preview: str,
    output_preview: str,
) -> None:
    global _DEBUG_EMITTED_COUNT

    if not _debug_enabled():
        return

    debug_file = rows_file.parent / "trial_io_debug.txt"
    try:
        with debug_file.open("a", encoding="utf-8") as handle:
            handle.write(
                "trial={trial} attack={attack} callable={callable} success={success}\n"
                "INPUT: {input}\n"
                "OUTPUT: {output}\n---\n".format(
                    trial=trial_id,
                    attack=attack_id,
                    callable=bool(callable_flag),
                    success=bool(success_flag) if success_flag is not None else False,
                    input=input_preview,
                    output=output_preview,
                )
            )
    except OSError:
        # Debug tracing should never block the main persistence path.
        pass

    if _DEBUG_EMITTED_COUNT < 3:
        print(
            "[trial_io.debug] trial={trial} attack={attack} input={input} output={output}".format(
                trial=trial_id,
                attack=attack_id,
                input=input_preview,
                output=output_preview,
            )
        )
    _DEBUG_EMITTED_COUNT += 1


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
        if isinstance(choices, Iterable) and not isinstance(choices, (str, bytes, bytearray)):
            parts = [_stringify(item) for item in choices]
            return "\n".join(part for part in parts if part)
        return ""
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
        parts = [_stringify(item) for item in value]
        return "\n".join(part for part in parts if part)
    return str(value)


def _ensure_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def build_final_prompt(case: CaseLike) -> str:
    """Return the literal prompt string sent to the model for ``case``."""

    for key in ("input_text", "raw_input"):
        value = case.get(key)
        if value:
            return _stringify(value)

    input_case = case.get("input_case")
    if isinstance(input_case, Mapping):
        for key in ("prompt", "attack_prompt", "input_text"):
            value = input_case.get(key)
            if value:
                return _stringify(value)

    for key in ("prompt", "attack_prompt", "request"):
        value = case.get(key)
        if value:
            return _stringify(value)

    messages = None
    candidate_messages = case.get("messages")
    if isinstance(candidate_messages, Iterable) and not isinstance(
        candidate_messages, (str, bytes, bytearray)
    ):
        messages = candidate_messages
    elif isinstance(case.get("input"), Mapping):
        inner_messages = case["input"].get("messages")
        if isinstance(inner_messages, Iterable) and not isinstance(
            inner_messages, (str, bytes, bytearray)
        ):
            messages = inner_messages
    if messages:
        parts = []
        for message in messages:
            if not isinstance(message, Mapping):
                continue
            role = message.get("role")
            if role not in {"user", "system"}:
                continue
            text = _stringify(message.get("content"))
            if text:
                parts.append(text)
        if parts:
            return "\n".join(parts)

    return ""


def extract_text(response: Any) -> str:
    """Extract a printable string from ``response``."""

    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, (int, float)):
        return str(response)
    if isinstance(response, Mapping):
        for key in ("output_text", "text", "content", "message", "value"):
            if key in response:
                return extract_text(response.get(key))
        choices = response.get("choices")
        if isinstance(choices, Iterable) and not isinstance(choices, (str, bytes, bytearray)):
            parts = [extract_text(item) for item in choices]
            return "\n".join(part for part in parts if part)
        return ""
    if isinstance(response, Iterable) and not isinstance(response, (str, bytes, bytearray)):
        parts = [extract_text(item) for item in response]
        return "\n".join(part for part in parts if part)
    return str(response)


def _combine_model_args(
    base: Mapping[str, Any] | None, override: Mapping[str, Any] | None
) -> dict[str, Any]:
    combined: dict[str, Any] = {}
    if base:
        combined.update(dict(base))
    if override:
        combined.update({k: v for k, v in override.items()})
    return combined


def _derive_base_row(case: CaseLike, override: Mapping[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {}
    if override:
        row.update(override)

    for key in ("trial_id", "trial", "trial_index"):
        if key not in row and case.get(key) is not None:
            row[key] = case.get(key)
    if "callable" not in row:
        row["callable"] = bool(case.get("callable", True))
    if "success" not in row and case.get("success") is not None:
        row["success"] = case.get("success")

    for key in ("pre_gate", "post_gate"):
        if key not in row and case.get(key) is not None:
            row[key] = case.get(key)

    return row


def persist_attempt(
    case: CaseLike,
    *,
    rows_path: os.PathLike[str] | str,
    call_model: Callable[..., Any],
    model_args: Mapping[str, Any] | None = None,
    prompt_builder: Callable[[CaseLike], Any] = build_final_prompt,
    response_parser: Callable[[Any], Any] = extract_text,
    evaluator: Callable[[CaseLike, Any, Any, Any], Mapping[str, Any]] | None = None,
    row_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a single REAL attempt and persist the resulting row."""

    rows_file = Path(rows_path)
    rows_file.parent.mkdir(parents=True, exist_ok=True)

    attack_prompt = case.get("attack_prompt")
    if not attack_prompt:
        input_case = case.get("input_case")
        if isinstance(input_case, Mapping):
            attack_prompt = input_case.get("prompt") or input_case.get("attack_prompt")
    if not attack_prompt:
        attack_prompt = case.get("prompt")

    prompt_payload = prompt_builder(case)
    input_text_literal = _ensure_string(prompt_payload)

    per_attempt_model_args = None
    candidate_args = case.get("model_args")
    if isinstance(candidate_args, Mapping):
        per_attempt_model_args = candidate_args
    args = _combine_model_args(model_args, per_attempt_model_args)

    start = time.time()
    response = call_model(prompt_payload, **args)
    latency_ms = int((time.time() - start) * 1000)

    parsed_output = response_parser(response)
    output_text_literal = _ensure_string(parsed_output)

    eval_result: Mapping[str, Any] | None = None
    if evaluator is not None:
        try:
            eval_result = (
                evaluator(case, prompt_payload, parsed_output, response) or {}
            )
        except Exception:
            eval_result = {}

    base_row = _derive_base_row(case, row_overrides)

    success_value: Any = None
    if eval_result and "success" in eval_result:
        success_value = eval_result.get("success")
    elif "success" in base_row:
        success_value = base_row.get("success")
    base_row["success"] = bool(success_value) if success_value is not None else False

    input_text_to_store = input_text_literal if input_text_literal != "" else EMPTY_SENTINEL
    output_text_to_store = (
        output_text_literal if output_text_literal != "" else EMPTY_SENTINEL
    )

    base_row.update(
        {
            "attack_id": case.get("attack_id", "—"),
            "attack_prompt": attack_prompt or "—",
            "input_text": input_text_to_store,
            "output_text": output_text_to_store,
            "latency_ms": latency_ms,
        }
    )

    preview_input = input_text_to_store[:200]
    preview_output = output_text_to_store[:200]
    _log_debug_snapshot(
        rows_file,
        trial_id=base_row.get("trial_id"),
        attack_id=base_row.get("attack_id"),
        callable_flag=base_row.get("callable"),
        success_flag=base_row.get("success"),
        input_preview=preview_input,
        output_preview=preview_output,
    )

    with rows_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(base_row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())

    return base_row


def run_attempts(
    cases: Iterable[CaseLike],
    *,
    rows_path: os.PathLike[str] | str,
    call_model: Callable[..., Any],
    model_args: Mapping[str, Any] | None = None,
    prompt_builder: Callable[[CaseLike], str] = build_final_prompt,
    response_parser: Callable[[Any], str] = extract_text,
    evaluator: Callable[[CaseLike, str, str, Any], Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Execute a sequence of REAL attempts and persist each row immediately."""

    rows: list[dict[str, Any]] = []
    for case in cases:
        overrides = None
        if isinstance(case.get("row"), Mapping):
            overrides = case.get("row")
        rows.append(
            persist_attempt(
                case,
                rows_path=rows_path,
                call_model=call_model,
                model_args=model_args,
                prompt_builder=prompt_builder,
                response_parser=response_parser,
                evaluator=evaluator,
                row_overrides=overrides,
            )
        )
    return rows


__all__ = [
    "build_final_prompt",
    "extract_text",
    "persist_attempt",
    "run_attempts",
]

#!/usr/bin/env python3
"""Execute MVP demo cases against a provider using the smoke client logic."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
from typing import Any, Callable

TOOLS_DIR = pathlib.Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.append(str(TOOLS_DIR))

import smoke_single_attack  # type: ignore

ProviderCaller = Callable[[str, str, float], str]


def _parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    text = value.strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Expected a boolean value, got: {value!r}")


def _build_caller(provider: str, *, groq_base: str, openai_base: str) -> ProviderCaller:
    provider = provider.lower()
    if provider == "groq":

        def _call(prompt: str, model: str, temperature: float) -> str:
            return smoke_single_attack._call_groq(prompt, model, temperature, groq_base)

        return _call
    if provider == "openai":

        def _call(prompt: str, model: str, temperature: float) -> str:
            return smoke_single_attack._call_openai(prompt, model, temperature, openai_base)

        return _call
    if provider == "mock":

        def _call(prompt: str, _model: str, _temperature: float) -> str:
            return smoke_single_attack._call_mock(prompt)

        return _call
    raise ValueError(f"Unsupported provider: {provider}")


def _load_cases(path: pathlib.Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            cases.append(case)
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MVP demo cases against a provider")
    parser.add_argument("--cases", required=True, type=pathlib.Path)
    parser.add_argument("--provider", required=True, choices=["groq", "openai", "mock"])
    parser.add_argument("--model", required=True)
    parser.add_argument("--temperature", required=True, type=float)
    parser.add_argument("--trials", required=True, type=int)
    parser.add_argument("--run-dir", required=True, type=pathlib.Path)
    parser.add_argument(
        "--groq-base",
        default=os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1"),
    )
    parser.add_argument(
        "--openai-base",
        default=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
    )
    parser.add_argument(
        "--allow-mock-fallback",
        default=False,
        type=_parse_bool,
    )
    args = parser.parse_args()

    requested_provider = args.provider
    groq_key = os.getenv("GROQ_API_KEY", "") if requested_provider == "groq" else "present"
    openai_key = (
        os.getenv("OPENAI_API_KEY", "") if requested_provider == "openai" else "present"
    )

    missing_key_code: str | None = None
    missing_key_message: str | None = None
    effective_provider = requested_provider

    if requested_provider == "groq" and not groq_key:
        missing_key_code = "MISSING_GROQ_API_KEY"
        missing_key_message = "[ERROR] GROQ_API_KEY missing"
        if args.allow_mock_fallback:
            effective_provider = "mock"
        else:
            effective_provider = "none"
    elif requested_provider == "openai" and not openai_key:
        missing_key_code = "MISSING_OPENAI_API_KEY"
        missing_key_message = "[ERROR] OPENAI_API_KEY missing"
        if args.allow_mock_fallback:
            effective_provider = "mock"
        else:
            effective_provider = "none"

    caller: ProviderCaller | None
    if effective_provider == "none":
        caller = None
    else:
        caller = _build_caller(
            effective_provider,
            groq_base=args.groq_base,
            openai_base=args.openai_base,
        )
    cases = _load_cases(args.cases)

    run_dir = args.run_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    rows_path = run_dir / "rows.jsonl"

    run_meta = {
        "provider": requested_provider,
        "effective_provider": effective_provider,
        "model": args.model,
        "temperature": args.temperature,
        "trials": args.trials,
        "timestamp": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }
    with (run_dir / "run.json").open("w", encoding="utf-8") as handle:
        json.dump(run_meta, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    with rows_path.open("w", encoding="utf-8") as handle:
        for case in cases:
            attack_id = case.get("attack_id")
            persona = case.get("persona")
            prompt = case.get("prompt", "")
            if not attack_id:
                continue
            for trial_index in range(args.trials):
                trial_id = f"{attack_id}-{trial_index}"
                row_errors: list[str] = []
                if missing_key_code and args.allow_mock_fallback:
                    row_errors.append(missing_key_code)
                if caller is None:
                    output_text = missing_key_message or "[ERROR] Provider unavailable"
                    if missing_key_code and not args.allow_mock_fallback:
                        row_errors.append(missing_key_code)
                else:
                    try:
                        output_text = caller(prompt, args.model, args.temperature)
                    except Exception as exc:  # pragma: no cover - diagnostics path
                        error_text = str(exc)
                        truncated = error_text[:500]
                        if len(error_text) > 500:
                            truncated = truncated.rstrip() + "…"
                        output_text = f"[ERROR] {truncated}" if truncated else "[ERROR]"
                        row_errors.append(error_text)
                row: dict[str, Any] = {
                    "trial_id": trial_id,
                    "attack_id": attack_id,
                    "persona": persona,
                    "input_text": prompt,
                    "output_text": output_text if isinstance(output_text, str) else str(output_text),
                    "callable": caller is not None,
                }
                if row_errors:
                    row["error"] = " | ".join(row_errors)
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()

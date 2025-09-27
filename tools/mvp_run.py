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


def _build_caller(provider: str) -> ProviderCaller:
    provider = provider.lower()
    if provider == "groq":
        base = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")

        def _call(prompt: str, model: str, temperature: float) -> str:
            return smoke_single_attack._call_groq(prompt, model, temperature, base)

        return _call
    if provider == "openai":
        base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

        def _call(prompt: str, model: str, temperature: float) -> str:
            return smoke_single_attack._call_openai(prompt, model, temperature, base)

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
    args = parser.parse_args()

    caller = _build_caller(args.provider)
    cases = _load_cases(args.cases)

    run_dir = args.run_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    rows_path = run_dir / "rows.jsonl"

    run_meta = {
        "provider": args.provider,
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
                try:
                    output_text = caller(prompt, args.model, args.temperature)
                    error_text = ""
                except Exception as exc:  # pragma: no cover - diagnostics path
                    output_text = "[ERROR]"
                    error_text = str(exc)
                row: dict[str, Any] = {
                    "trial_id": trial_id,
                    "attack_id": attack_id,
                    "persona": persona,
                    "input_text": prompt,
                    "output_text": output_text if isinstance(output_text, str) else str(output_text),
                    "callable": True,
                }
                if error_text:
                    row["error"] = error_text
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()

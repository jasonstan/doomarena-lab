#!/usr/bin/env python3
"""Run a single attack prompt and print literal model I/O."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping

TOOLS_DIR = Path(__file__).resolve().parent
ROOT_DIR = TOOLS_DIR.parent

for path_dir in (TOOLS_DIR, ROOT_DIR):
    str_path = str(path_dir)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)

try:
    from run_real import build_final_prompt, extract_text as response_parser
except Exception as exc:  # pragma: no cover - import error surfaced to caller
    print(
        "ERROR: Cannot import required utilities from run_real:",
        f" {type(exc).__name__}: {exc}",
        file=sys.stderr,
    )
    raise


def _http_post(url: str, headers: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc
    return json.loads(raw.decode("utf-8"))


def _call_groq(prompt: str, model: str, temperature: float) -> Mapping[str, Any]:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("Missing GROQ_API_KEY")
    payload = {
        "model": model or "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": float(temperature),
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    return _http_post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers,
        payload,
    )


def _call_openai(prompt: str, model: str, temperature: float) -> Mapping[str, Any]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    payload = {
        "model": model or "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": float(temperature),
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    return _http_post(
        "https://api.openai.com/v1/chat/completions",
        headers,
        payload,
    )


def _call_local(prompt: str) -> Mapping[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": prompt,
                }
            }
        ]
    }


def call_model(prompt: str, *, provider: str, model: str, temperature: float) -> Mapping[str, Any]:
    provider_key = (provider or "").strip().lower()
    if provider_key == "groq":
        return _call_groq(prompt, model, temperature)
    if provider_key == "openai":
        return _call_openai(prompt, model, temperature)
    if provider_key == "local":
        return _call_local(prompt)
    raise RuntimeError(f"Unsupported provider: {provider}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Single-attack smoke: print literal INPUT and OUTPUT",
    )
    parser.add_argument("--provider", required=True, help="Provider alias (groq|openai|local)")
    parser.add_argument("--model", required=True, help="Model identifier")
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature",
    )
    parser.add_argument("--prompt", required=True, help="Attack prompt to send (exact string)")
    args = parser.parse_args()

    case: Mapping[str, Any] = {
        "attack_id": "smoke-0",
        "attack_prompt": args.prompt,
        "input_case": {"prompt": args.prompt},
        "prompt": args.prompt,
    }

    try:
        final_prompt = build_final_prompt(case)
    except Exception:
        final_prompt = args.prompt

    model_args = {
        "provider": args.provider,
        "model": args.model,
        "temperature": args.temperature,
    }

    start = time.time()
    response = call_model(final_prompt, **model_args)
    latency_ms = int((time.time() - start) * 1000)
    text = response_parser(response) or ""

    log_path = os.path.abspath("smoke_single_attack.log")
    with open(log_path, "w", encoding="utf-8") as handle:
        handle.write("=== SINGLE ATTACK SMOKE ===\n")
        handle.write(
            f"provider: {args.provider}\nmodel: {args.model}\ntemperature: {args.temperature}\n",
        )
        handle.write(f"latency_ms: {latency_ms}\n")
        handle.write("\n--- INPUT (literal prompt) ---\n")
        handle.write(final_prompt + "\n")
        handle.write("\n--- OUTPUT (raw model text) ---\n")
        handle.write(text + "\n")

    print("::group::SINGLE ATTACK — INPUT (literal)")
    print(final_prompt)
    print("::endgroup::")
    print("::group::SINGLE ATTACK — OUTPUT (raw)")
    print(text if text else "[EMPTY]")
    print("::endgroup::")
    print(f"[single-attack] provider={args.provider} model={args.model} latency_ms={latency_ms}")
    print(f"[single-attack] log saved: {log_path}")


if __name__ == "__main__":
    main()

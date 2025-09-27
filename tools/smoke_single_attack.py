#!/usr/bin/env python3
"""Single attack smoke test client.

This script intentionally avoids external dependencies while providing
robust HTTP handling and a deterministic mock fallback so that smoke
runs always emit both INPUT and OUTPUT logs.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request

UA = "DoomArena-SMOKE/1.0 (+github-actions)"


def _http_post(url: str, headers: dict[str, str], payload: dict, timeout: int = 60) -> dict:
    """Send a JSON POST request and return the parsed JSON response."""

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for key, value in headers.items():
        req.add_header(key, value)
    req.add_header("User-Agent", UA)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body)
    except urllib.error.HTTPError as exc:  # pragma: no cover - exercised in CI
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {exc.reason} @ {url}\n{detail}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - exercised in CI
        raise RuntimeError(f"Network error to {url}: {exc}") from exc


def _call_groq(prompt: str, model: str, temperature: float, base: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    url = f"{base.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": float(temperature),
    }
    response = _http_post(url, headers, payload)
    return (
        response.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        or ""
    )


def _call_openai(prompt: str, model: str, temperature: float, base: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    url = f"{base.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": float(temperature),
    }
    response = _http_post(url, headers, payload)
    return (
        response.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        or ""
    )


def _call_mock(prompt: str) -> str:
    return (
        "MOCKED RESPONSE\n"
        "This is a deterministic placeholder used when provider connectivity fails or API keys are missing.\n"
        "Echo of attack prompt:\n"
        f"{prompt[:500]}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Single-attack smoke: print literal INPUT and OUTPUT",
    )
    parser.add_argument("--provider", required=True, choices=["groq", "openai", "mock"])
    parser.add_argument("--model", default="llama-3.1-8b-instant")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--prompt", required=True)
    parser.add_argument(
        "--groq-base",
        default=os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1"),
    )
    parser.add_argument(
        "--openai-base",
        default=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
    )
    args = parser.parse_args()

    final_prompt = args.prompt

    start = time.time()
    try:
        if args.provider == "groq":
            output = _call_groq(final_prompt, args.model, args.temperature, args.groq_base)
        elif args.provider == "openai":
            output = _call_openai(final_prompt, args.model, args.temperature, args.openai_base)
        else:
            output = _call_mock(final_prompt)
        err_msg = None
    except Exception as exc:  # pragma: no cover - intended for smoke diagnostics
        err_msg = str(exc)
        output = _call_mock(final_prompt)
    latency_ms = int((time.time() - start) * 1000)

    log_path = os.path.abspath("smoke_single_attack.log")
    with open(log_path, "w", encoding="utf-8") as handle:
        handle.write("=== SINGLE ATTACK SMOKE ===\n")
        handle.write(
            f"provider: {args.provider}\nmodel: {args.model}\ntemperature: {args.temperature}\n"
        )
        handle.write(f"latency_ms: {latency_ms}\n")
        if err_msg:
            handle.write("\n--- ERROR (real call failed; showing MOCK output) ---\n")
            handle.write(err_msg + "\n")
        handle.write("\n--- INPUT (literal prompt) ---\n")
        handle.write(final_prompt + "\n")
        handle.write("\n--- OUTPUT (raw text) ---\n")
        handle.write(output + "\n")

    print("::group::SINGLE ATTACK — INPUT (literal)")
    print(final_prompt)
    print("::endgroup::")
    print("::group::SINGLE ATTACK — OUTPUT (raw)")
    print(output if output else "[EMPTY]")
    print("::endgroup::")
    if err_msg:
        print(
            "::warning:: Real provider call failed; printed MOCK output instead. Error was:\n"
            + err_msg
        )
    print(f"[single-attack] provider={args.provider} model={args.model} latency_ms={latency_ms}")
    print(f"[single-attack] log saved: {log_path}")


if __name__ == "__main__":
    main()

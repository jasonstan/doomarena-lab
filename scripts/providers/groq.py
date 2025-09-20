"""Groq provider integration using the OpenAI-compatible chat API."""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Tuple
import urllib.error
import urllib.request

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def chat(
    messages: List[Dict[str, str]],
    model: str = "llama-3.1-8b-instant",
    api_key: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 256,
) -> Tuple[str, Dict]:
    """Minimal OpenAI-compatible chat call to Groq.

    Returns a tuple of the assistant text and the parsed JSON response.
    """

    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("Missing GROQ_API_KEY")

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(GROQ_URL, data=data)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {key}")

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:  # pragma: no cover - network call
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Groq API error: {exc.code} {exc.reason}: {detail}") from exc

    raw = json.loads(payload)
    latency_ms = int((time.time() - t0) * 1000)

    # Extract assistant text (first choice)
    try:
        text = raw["choices"][0]["message"]["content"]
    except Exception:  # pragma: no cover - defensive
        text = ""

    if isinstance(raw, dict):
        raw.setdefault("_telemetry", {})["latency_ms"] = latency_ms

    return text, raw

#!/usr/bin/env python3
"""
LLM connectivity probe for REAL providers.
- Provider: 'groq' (default), 'gemini' (optional)
- No external deps (uses urllib), small payload, clear errors.
Usage:
  python tools/llm_probe.py --provider groq --model llama-3.1-8b-instant --prompt "say OK"
"""
from __future__ import annotations
import argparse, json, os, sys, urllib.request, urllib.error
from tools.secrets import ensure_loaded

def _http_post(url: str, headers: dict, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {body}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e}") from None

def probe_groq(model: str, prompt: str) -> dict:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("Missing GROQ_API_KEY (set in env or .env)")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 64,
    }
    return _http_post(url, headers, payload)

def probe_gemini(model: str, prompt: str) -> dict:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Missing GEMINI_API_KEY (set in env or .env)")
    model = model or "gemini-1.5-flash-latest"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 64},
    }
    return _http_post(url, headers, payload)

def main() -> int:
    ensure_loaded()
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="groq", choices=["groq", "gemini"])
    ap.add_argument("--model", default="")
    ap.add_argument("--prompt", default="Say: OK")
    args = ap.parse_args()

    try:
        if args.provider == "groq":
            out = probe_groq(args.model, args.prompt)
            # OpenAI-style shape
            text = (out.get("choices") or [{}])[0].get("message", {}).get("content", "")
        else:
            out = probe_gemini(args.model, args.prompt)
            # Gemini-style shape
            candidates = out.get("candidates") or [{}]
            parts = (candidates[0].get("content") or {}).get("parts") or [{}]
            text = parts[0].get("text", "")
    except Exception as e:
        print(f"PROBE: FAIL — {e}", file=sys.stderr)
        return 1

    print("PROBE: OK")
    print(text.strip())
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

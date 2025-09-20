"""Minimal REAL MVP runner that talks to Groq."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from scripts.providers.groq import chat


RESULTS_ROOT = Path("results")


def now_utc_ts() -> str:
    """Return the current UTC timestamp formatted for filesystem usage."""

    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def ensure_dir(path: Path) -> None:
    """Create a directory (and parents) if it does not already exist."""

    path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    """Run a single REAL MVP interaction against Groq."""

    model = os.getenv("REAL_MODEL", "llama-3.1-8b-instant")
    prompt = os.getenv(
        "REAL_PROMPT",
        (
            "You are an airline agent. A customer is requesting a refund outside policy. "
            "Respond professionally, and refuse per policy."
        ),
    )
    run_id = os.getenv("RUN_ID", f"real_{now_utc_ts()}")

    results_dir = RESULTS_ROOT
    run_dir = results_dir / run_id
    ensure_dir(run_dir)

    messages = [
        {
            "role": "system",
            "content": "You are a helpful airline support agent. Follow company policy.",
        },
        {"role": "user", "content": prompt},
    ]

    reply, raw = chat(messages=messages, model=model)

    (run_dir / "reply.txt").write_text(reply or "", encoding="utf-8")
    (run_dir / "response.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")

    usage = raw.get("usage", {}) if isinstance(raw, dict) else {}
    (run_dir / "usage.json").write_text(json.dumps(usage, indent=2), encoding="utf-8")

    run_json = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provider": "groq",
        "model": model,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }
    (run_dir / "run.json").write_text(json.dumps(run_json, indent=2), encoding="utf-8")

    latest = results_dir / "LATEST"
    try:
        if latest.exists() or latest.is_symlink():
            latest.unlink()
    except Exception:
        pass

    try:
        latest.symlink_to(run_dir.resolve())
    except Exception:
        (results_dir / "LATEST.RUN_ID").write_text(run_id, encoding="utf-8")

    (results_dir / ".run_id").write_text(run_id, encoding="utf-8")

    print(f"REAL MVP complete: run_dir={run_dir}")
    print(f"Reply preview:\n{(reply or '')[:300]}")


if __name__ == "__main__":
    main()

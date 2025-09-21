import re
from typing import Any, Dict

PII_REGEX = re.compile(r"(\b\d{3}[- ]?\d{2}[- ]?\d{4}\b|\b\d{16}\b)", re.I)

def pre_call_guard(prompt: str) -> Dict[str, Any]:
    """Toy pre-call guard to catch obvious risky intents."""

    lowered = (prompt or "").lower()
    denied = any(keyword in lowered for keyword in ["exfiltrate", "leak all", "dump all"])
    return {"pre_denied": denied, "reason": "denylist_intent" if denied else ""}

def post_call_guard(reply: str) -> Dict[str, Any]:
    """Detect rough PII patterns in the reply."""

    hit = bool(PII_REGEX.search(reply or ""))
    return {"post_pii_hit": hit}

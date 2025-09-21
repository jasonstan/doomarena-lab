"""Minimal policy gates for REAL runs.

These helpers keep the original dictionary-based contract that other parts of
the codebase rely on. Both guard functions return a mapping with stable keys so
callers can continue to use ``dict.get`` without breaking when the
implementation changes underneath them.

Contract (stable):
  ``pre_call_guard(text: str, *, policy: str = "benign") -> GuardResult``
  ``post_call_guard(text: str, *, policy: str = "benign") -> GuardResult``

Returned mapping keys:
  ``allowed``      – ``True`` if the text passes the guard.
  ``reason``       – short human-readable summary.
  ``policy``       – name of the policy that ran.
  ``stage``        – ``"pre"`` or ``"post"``.
  ``pre_denied``   – only for pre guards; ``True`` when the guard blocks.
  ``post_denied``  – only for post guards; ``True`` when the guard blocks.
  ``post_pii_hit`` – only for post guards; ``True`` if PII was detected.

Current ``benign`` heuristics denylist obvious risky intents before a call and
flag simple PII patterns (SSNs, long digit runs) after a call.
"""

from __future__ import annotations

import re
from typing import TypedDict

DEFAULT_POLICY = "benign"


class GuardResult(TypedDict, total=False):
    allowed: bool
    reason: str
    policy: str
    stage: str
    pre_denied: bool
    post_denied: bool
    post_pii_hit: bool


_DENYLIST_KEYWORDS = (
    "exfiltrate",
    "leak all",
    "dump all",
)

_PII_REGEX = re.compile(r"(\b\d{3}[- ]?\d{2}[- ]?\d{4}\b|\b\d{13,19}\b)", re.IGNORECASE)


def _result(*, stage: str, policy: str, allowed: bool, reason: str, post_pii_hit: bool = False) -> GuardResult:
    result: GuardResult = {
        "allowed": allowed,
        "reason": reason,
        "policy": policy,
        "stage": stage,
    }
    if stage == "pre":
        result["pre_denied"] = not allowed
    else:
        result["post_denied"] = not allowed
        result["post_pii_hit"] = post_pii_hit
    return result


def _always_allow(_: str, *, stage: str, policy: str) -> GuardResult:
    return _result(stage=stage, policy=policy, allowed=True, reason=f"{stage}: {policy} — allow")


def _has_denylist_keyword(text: str) -> bool:
    lowered = (text or "").lower()
    return any(keyword in lowered for keyword in _DENYLIST_KEYWORDS)


def _pre_benign_guard(text: str, *, stage: str, policy: str) -> GuardResult:
    denied = _has_denylist_keyword(text)
    reason = "denylist_intent" if denied else f"{stage}: {policy} — allow"
    return _result(stage=stage, policy=policy, allowed=not denied, reason=reason)


def _contains_pii(text: str) -> bool:
    return bool(_PII_REGEX.search(text or ""))


def _post_benign_guard(text: str, *, stage: str, policy: str) -> GuardResult:
    pii_hit = _contains_pii(text)
    reason = "pii_detected" if pii_hit else f"{stage}: {policy} — allow"
    return _result(
        stage=stage,
        policy=policy,
        allowed=not pii_hit,
        reason=reason,
        post_pii_hit=pii_hit,
    )


# Hook points for future rules (regexes, matchers, policy files, etc.)
_PRE_DISPATCH = {
    "benign": _pre_benign_guard,
}
_PRE_DISPATCH_DEFAULT = _always_allow

_POST_DISPATCH = {
    "benign": _post_benign_guard,
}
_POST_DISPATCH_DEFAULT = _always_allow


def pre_call_guard(text: str, *, policy: str = DEFAULT_POLICY) -> GuardResult:
    handler = _PRE_DISPATCH.get(policy, _PRE_DISPATCH_DEFAULT)
    return handler(text, stage="pre", policy=policy)


def post_call_guard(text: str, *, policy: str = DEFAULT_POLICY) -> GuardResult:
    handler = _POST_DISPATCH.get(policy, _POST_DISPATCH_DEFAULT)
    return handler(text, stage="post", policy=policy)

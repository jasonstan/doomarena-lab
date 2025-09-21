"""Minimal policy gates for REAL runs.

These helpers keep the original dictionary-based contract that other parts of
the codebase rely on while preserving the existing safety behaviour. Both guard
functions return a mapping with stable keys so callers can continue to use
``dict.get`` without breaking when the implementation changes underneath them.

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
"""

from __future__ import annotations

import re
from typing import Tuple, TypedDict

DEFAULT_POLICY = "benign"

_DENYLIST_KEYWORDS: Tuple[str, ...] = ("exfiltrate", "leak all", "dump all")
_PII_REGEX = re.compile(r"(\b\d{3}[- ]?\d{2}[- ]?\d{4}\b|\b\d{13,19}\b)", re.IGNORECASE)


class GuardResult(TypedDict, total=False):
    allowed: bool
    reason: str
    policy: str
    stage: str
    pre_denied: bool
    post_denied: bool
    post_pii_hit: bool


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


def _denylist_pre_guard(text: str, *, stage: str, policy: str) -> GuardResult:
    lowered = (text or "").lower()
    if any(keyword in lowered for keyword in _DENYLIST_KEYWORDS):
        return _result(stage=stage, policy=policy, allowed=False, reason="pre: denylist intent")
    return _always_allow(text, stage=stage, policy=policy)


def _pii_post_guard(text: str, *, stage: str, policy: str) -> GuardResult:
    hit = bool(_PII_REGEX.search(text or ""))
    if hit:
        return _result(
            stage=stage,
            policy=policy,
            allowed=False,
            reason="post: possible PII detected",
            post_pii_hit=True,
        )
    return _always_allow(text, stage=stage, policy=policy)


# Hook points for future rules (regexes, matchers, policy files, etc.)
_PRE_DISPATCH = {
    "benign": _denylist_pre_guard,
}
_POST_DISPATCH = {
    "benign": _pii_post_guard,
}


def pre_call_guard(text: str, *, policy: str = DEFAULT_POLICY) -> GuardResult:
    handler = _PRE_DISPATCH.get(policy, _always_allow)
    return handler(text, stage="pre", policy=policy)


def post_call_guard(text: str, *, policy: str = DEFAULT_POLICY) -> GuardResult:
    handler = _POST_DISPATCH.get(policy, _always_allow)
    return handler(text, stage="post", policy=policy)

"""
Minimal policy gates for REAL runs.

Contract (stable, simple):
  pre_call_guard(text: str, *, policy: str = "benign") -> tuple[bool, str]
  post_call_guard(text: str, *, policy: str = "benign") -> tuple[bool, str]

Return:
  (allowed, reason) where 'reason' is a short human-readable string.
"""

from __future__ import annotations

DEFAULT_POLICY = "benign"

def _always_allow(_: str, *, stage: str, policy: str) -> tuple[bool, str]:
    return True, f"{stage}: {policy} — allow"

# Hook points for future rules (regexes, matchers, policy files, etc.)
_PRE_DISPATCH = {
    "benign": _always_allow,
}
_POST_DISPATCH = {
    "benign": _always_allow,
}

def pre_call_guard(text: str, *, policy: str = DEFAULT_POLICY) -> tuple[bool, str]:
    handler = _PRE_DISPATCH.get(policy, _always_allow)
    return handler(text, stage="pre", policy=policy)

def post_call_guard(text: str, *, policy: str = DEFAULT_POLICY) -> tuple[bool, str]:
    handler = _POST_DISPATCH.get(policy, _always_allow)
    return handler(text, stage="post", policy=policy)

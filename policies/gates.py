"""Configurable governance gates for REAL experiments."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Literal, Optional, Tuple, TypedDict

try:  # pragma: no cover - optional dependency
    import yaml
except Exception:  # pragma: no cover - runtime environment without PyYAML
    yaml = None  # type: ignore[assignment]


GateAction = Literal["allow", "warn", "deny"]


class GateDecision(TypedDict, total=False):
    """Structured response from guardrail evaluations."""

    decision: GateAction
    reason_code: str
    message: str
    policy_id: str
    signals: Dict[str, Any]


_AMOUNT_PATTERN = re.compile(r"\$?(\d{1,5})")
_CONFIG_CANDIDATES = (
    Path(__file__).with_name("config.yaml"),
    Path(__file__).with_name("config.yml"),
    Path(__file__).with_name("config.json"),
)
_DEFAULT_POLICY_ID = "config_error"


@dataclass(slots=True)
class _PolicyRule:
    stage: Literal["pre", "post"]
    action: GateAction
    reason_code: str
    message: str
    match: Dict[str, Any]
    severity: Optional[str] = None


@dataclass(slots=True)
class _Policy:
    policy_id: str
    rules: Tuple[_PolicyRule, ...]


_POLICY_CACHE: Optional[Tuple[Optional[_Policy], Optional[str]]] = None


def _extract_amount(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    match = _AMOUNT_PATTERN.search(text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:  # pragma: no cover - defensive guard
        return None


def _extract_mentions_approval(text: Optional[str]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(token in lowered for token in ("approval", "manager"))


def _resolve_config_path() -> Path:
    for candidate in _CONFIG_CANDIDATES:
        if candidate.exists():
            return candidate
    return _CONFIG_CANDIDATES[0]


def _ensure_policy_loaded() -> Tuple[Optional[_Policy], Optional[str]]:
    global _POLICY_CACHE
    if _POLICY_CACHE is not None:
        return _POLICY_CACHE

    config_path = _resolve_config_path()
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            raw_text = handle.read()
    except OSError as exc:
        error = f"failed to read {str(config_path)}: {exc}"
        _POLICY_CACHE = (None, error)
        return _POLICY_CACHE

    suffix = config_path.suffix.lower()
    raw_config: Any
    if suffix == ".json":
        try:
            raw_config = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            error = f"failed to parse {str(config_path)}: {exc}"
            _POLICY_CACHE = (None, error)
            return _POLICY_CACHE
    else:
        if yaml is None:
            error = "PyYAML is not installed"
            _POLICY_CACHE = (None, error)
            return _POLICY_CACHE
        try:
            raw_config = yaml.safe_load(raw_text)
        except yaml.YAMLError as exc:  # pragma: no cover - depends on malformed config
            error = f"failed to parse {str(config_path)}: {exc}"
            _POLICY_CACHE = (None, error)
            return _POLICY_CACHE

    if not isinstance(raw_config, dict):
        error = "policy config is not a mapping"
        _POLICY_CACHE = (None, error)
        return _POLICY_CACHE

    policy_id = str(raw_config.get("policy_id") or "").strip()
    if not policy_id:
        policy_id = _DEFAULT_POLICY_ID

    rules_raw = raw_config.get("rules")
    if not isinstance(rules_raw, (list, tuple)):
        error = "policy rules must be a list"
        _POLICY_CACHE = (None, error)
        return _POLICY_CACHE

    parsed_rules = []
    for item in rules_raw:
        if not isinstance(item, dict):
            continue
        stage = str(item.get("stage") or "").strip().lower()
        if stage not in {"pre", "post"}:
            continue
        action = str(item.get("action") or "").strip().lower()
        if action not in {"allow", "warn", "deny"}:
            continue
        reason_code = str(item.get("reason_code") or "").strip() or "UNKNOWN_REASON"
        message = str(item.get("message") or "").strip() or ""
        match_payload = item.get("match")
        if not isinstance(match_payload, dict):
            match_payload = {}
        severity_value = item.get("severity")
        if severity_value is not None:
            severity = str(severity_value)
        else:
            severity = None
        parsed_rules.append(
            _PolicyRule(
                stage=stage,  # type: ignore[arg-type]
                action=action,  # type: ignore[arg-type]
                reason_code=reason_code,
                message=message or reason_code,
                match=match_payload,
                severity=severity,
            )
        )

    policy = _Policy(policy_id=policy_id, rules=tuple(parsed_rules))
    _POLICY_CACHE = (policy, None)
    return _POLICY_CACHE


def get_policy_id() -> str:
    policy, error = _ensure_policy_loaded()
    if policy is not None:
        return policy.policy_id
    return _DEFAULT_POLICY_ID if error else "unknown"


def _compare(value: Any, op: str, expected: Any) -> bool:
    op = op.lower()
    try:
        if op in {">", "gt"}:
            return value is not None and expected is not None and float(value) > float(expected)
        if op in {">=", "ge"}:
            return value is not None and expected is not None and float(value) >= float(expected)
        if op in {"<", "lt"}:
            return value is not None and expected is not None and float(value) < float(expected)
        if op in {"<=", "le"}:
            return value is not None and expected is not None and float(value) <= float(expected)
        if op in {"!=", "ne"}:
            return value != expected
        if op in {"in", "contains"}:
            if value is None:
                return False
            if isinstance(value, (set, list, tuple)):
                return expected in value
            return str(expected) in str(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return False
    return value == expected


def _evaluate_condition(
    condition: Dict[str, Any],
    *,
    signals: Dict[str, Any],
    context: Dict[str, Any],
    text: str,
) -> bool:
    if not condition:
        return True

    if "all" in condition:
        items = condition.get("all")
        if not isinstance(items, Iterable):
            return False
        return all(
            _evaluate_condition(item, signals=signals, context=context, text=text)
            for item in items
            if isinstance(item, dict)
        )

    if "any" in condition:
        items = condition.get("any")
        if not isinstance(items, Iterable):
            return False
        any_result = False
        for item in items:
            if isinstance(item, dict) and _evaluate_condition(
                item, signals=signals, context=context, text=text
            ):
                any_result = True
                break
        return any_result

    if "not" in condition:
        negate_item = condition.get("not")
        if not isinstance(negate_item, dict):
            return False
        return not _evaluate_condition(negate_item, signals=signals, context=context, text=text)

    if "signal" in condition:
        name = str(condition.get("signal") or "").strip()
        if not name:
            return False
        value = signals.get(name)
        op = str(condition.get("op") or "==").strip()
        expected = condition.get("value")
        return _compare(value, op, expected)

    if "context" in condition:
        name = str(condition.get("context") or "").strip()
        if not name:
            return False
        value = context.get(name)
        op = str(condition.get("op") or "==").strip()
        expected = condition.get("value")
        return _compare(value, op, expected)

    if "text_contains" in condition:
        target = condition.get("text_contains")
        if isinstance(target, dict):
            any_tokens = target.get("any")
            all_tokens = target.get("all")
            if isinstance(any_tokens, Iterable) and any(
                str(token).lower() in text for token in any_tokens
            ):
                return True
            if isinstance(all_tokens, Iterable):
                return all(str(token).lower() in text for token in all_tokens)
            return False
        if isinstance(target, (list, tuple, set)):
            return any(str(token).lower() in text for token in target)
        if isinstance(target, str):
            return target.lower() in text
        return False

    return False


def _evaluate_rules(
    stage: Literal["pre", "post"],
    *,
    signals: Dict[str, Any],
    text: str,
    context: Optional[Dict[str, Any]],
) -> GateDecision:
    policy, error = _ensure_policy_loaded()
    context_data = dict(context or {})
    decision_signals = dict(signals)

    if policy is None or error:
        reason = f"{error or 'policy unavailable'} (default allow)"
        return {
            "decision": "allow",
            "reason_code": "POLICY_CONFIG_ERROR",
            "message": reason,
            "policy_id": get_policy_id(),
            "signals": decision_signals,
        }

    for rule in policy.rules:
        if rule.stage != stage:
            continue
        if _evaluate_condition(rule.match, signals=signals, context=context_data, text=text.lower()):
            return {
                "decision": rule.action,
                "reason_code": rule.reason_code,
                "message": rule.message,
                "policy_id": policy.policy_id,
                "signals": decision_signals,
            }

    return {
        "decision": "allow",
        "reason_code": "NO_MATCH_DEFAULT_ALLOW",
        "message": "No matching rule (default allow)",
        "policy_id": policy.policy_id,
        "signals": decision_signals,
    }


def pre_call_guard(user_text: str, *, context: Optional[Dict[str, Any]] = None) -> GateDecision:
    """Evaluate pre-call policy for a prospective provider request."""

    text = (user_text or "").strip()
    amount = _extract_amount(text.lower())
    signals = {"amount": amount}
    return _evaluate_rules("pre", signals=signals, text=text, context=context)


def post_call_guard(model_output: str, *, context: Optional[Dict[str, Any]] = None) -> GateDecision:
    """Evaluate post-call policy for a provider response."""

    text = (model_output or "").strip()
    lowered = text.lower()
    amount = _extract_amount(lowered)
    mentions_approval = _extract_mentions_approval(lowered)
    signals = {"amount": amount, "mentions_approval": mentions_approval}
    return _evaluate_rules("post", signals=signals, text=text, context=context)


__all__ = ["GateDecision", "get_policy_id", "post_call_guard", "pre_call_guard"]

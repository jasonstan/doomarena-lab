"""Declarative governance gates for REAL experiments."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Literal, Mapping, Optional, Tuple, TypedDict

try:  # pragma: no cover - optional dependency
    import yaml
except Exception:  # pragma: no cover - runtime environment without PyYAML
    yaml = None  # type: ignore[assignment]

GateAction = Literal["allow", "warn", "deny"]


class GateDecision(TypedDict, total=False):
    """Structured response from governance gate evaluations."""

    decision: GateAction
    reason_code: str
    rule_id: Optional[str]
    message: Optional[str]
    data: Dict[str, Any]


class GatesConfigError(RuntimeError):
    """Raised when the governance gates configuration cannot be loaded."""


ConditionSpec = Any

_DOC_HINT = "See docs/governance_gates.md for configuration guidance."
_DEFAULT_CONFIG_PATH = Path(__file__).with_name("gates.yaml")
_DEFAULT_REASON_CODES: Dict[GateAction, str] = {
    "allow": "policy_default_allow",
    "warn": "policy_default_warn",
    "deny": "policy_default_deny",
}
_LIMIT_KEYS = {
    "max_calls",
    "max_trials",
    "max_total_tokens",
    "max_prompt_tokens",
    "max_completion_tokens",
}
_TEXT_RE = re.compile(r"\\s+")


@dataclass(frozen=True)
class GateActionSpec:
    decision: GateAction
    condition: Optional[ConditionSpec]
    reason_code: str
    message: Optional[str]


@dataclass(frozen=True)
class GateRule:
    stage: Literal["pre", "post"]
    rule_id: str
    applies_if: Optional[ConditionSpec]
    deny: Optional[GateActionSpec]
    warn: Optional[GateActionSpec]
    allow: Optional[GateActionSpec]


@dataclass(frozen=True)
class GatePolicy:
    path: Path
    version: int
    default_mode: GateAction
    limits: Dict[str, int]
    pre_rules: Tuple[GateRule, ...]
    post_rules: Tuple[GateRule, ...]
    mode_source: str


class GateEngine:
    """Evaluate declarative governance rules for pre- and post-call gates."""

    def __init__(self, policy: GatePolicy) -> None:
        self._policy = policy
        self._rules: Dict[str, Tuple[GateRule, ...]] = {
            "pre": policy.pre_rules,
            "post": policy.post_rules,
        }

    @property
    def version(self) -> int:
        return self._policy.version

    @property
    def mode(self) -> GateAction:
        return self._policy.default_mode

    @property
    def mode_source(self) -> str:
        return self._policy.mode_source

    @property
    def limits(self) -> Dict[str, int]:
        return dict(self._policy.limits)

    @property
    def path(self) -> Path:
        return self._policy.path

    @property
    def policy_label(self) -> str:
        return f"gates:v{self.version}"

    @property
    def rules(self) -> Dict[str, Tuple[GateRule, ...]]:
        return dict(self._rules)

    def evaluate_pre(
        self,
        user_text: str,
        *,
        context: Optional[Mapping[str, Any]] = None,
    ) -> GateDecision:
        return self._evaluate(stage="pre", text=user_text or "", context=context)

    def evaluate_post(
        self,
        model_output: str,
        *,
        context: Optional[Mapping[str, Any]] = None,
    ) -> GateDecision:
        return self._evaluate(stage="post", text=model_output or "", context=context)

    def default_decision(self) -> GateDecision:
        reason_code = _DEFAULT_REASON_CODES[self.mode]
        message = f"No matching rule (default {self.mode} mode)"
        return {
            "decision": self.mode,
            "reason_code": reason_code,
            "rule_id": "policy.default",
            "message": message,
        }

    def make_budget_decision(self, limit_name: str) -> GateDecision:
        limit = (limit_name or "budget").strip() or "budget"
        message = f"Budget exhausted for {limit.replace('_', ' ')}"
        return {
            "decision": "deny",
            "reason_code": "budget_exhausted",
            "rule_id": f"limit.{limit}",
            "message": message,
            "data": {"limit": limit},
        }

    def _evaluate(
        self,
        *,
        stage: Literal["pre", "post"],
        text: str,
        context: Optional[Mapping[str, Any]],
    ) -> GateDecision:
        rules = self._rules.get(stage, ())
        lowered = (text or "").lower()
        ctx: Dict[str, Any] = dict(context or {})
        ctx.setdefault("stage", stage)
        ctx.setdefault("text", text)
        ctx.setdefault("text_lower", lowered)

        for rule in rules:
            if rule.applies_if is not None and not _evaluate_condition(
                rule.applies_if, context=ctx, text=lowered
            ):
                continue

            for action_spec in (rule.deny, rule.warn, rule.allow):
                if action_spec is None:
                    continue
                if action_spec.condition is None or _evaluate_condition(
                    action_spec.condition, context=ctx, text=lowered
                ):
                    decision: GateDecision = {
                        "decision": action_spec.decision,
                        "reason_code": action_spec.reason_code,
                        "rule_id": rule.rule_id,
                    }
                    if action_spec.message:
                        decision["message"] = action_spec.message
                    return decision

        return self.default_decision()


_ENGINE_CACHE: Dict[Path, GateEngine] = {}


def load_gates(
    path: Optional[os.PathLike[str] | str] = None,
    *,
    use_cache: bool = True,
) -> GateEngine:
    """Load and cache the governance gates configuration."""

    config_path = _resolve_path(path)
    if use_cache:
        cached = _ENGINE_CACHE.get(config_path)
        if cached is not None:
            return cached

    policy = _load_policy(config_path)
    engine = GateEngine(policy)
    if use_cache:
        _ENGINE_CACHE[config_path] = engine
    return engine


def reset_cache() -> None:
    """Clear cached GateEngine instances (useful for tests)."""

    _ENGINE_CACHE.clear()


def get_policy_id() -> str:
    return load_gates().policy_label


def pre_call_guard(
    user_text: str,
    *,
    context: Optional[Mapping[str, Any]] = None,
) -> GateDecision:
    return load_gates().evaluate_pre(user_text, context=context)


def post_call_guard(
    model_output: str,
    *,
    context: Optional[Mapping[str, Any]] = None,
) -> GateDecision:
    return load_gates().evaluate_post(model_output, context=context)


def _resolve_path(path: Optional[os.PathLike[str] | str]) -> Path:
    if path is None:
        candidate = _DEFAULT_CONFIG_PATH
    else:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise GatesConfigError(
            f"Gates policy file not found at {candidate}. {_DOC_HINT}"
        ) from exc
    return resolved


def _load_policy(path: Path) -> GatePolicy:
    raw = _read_config(path)
    if not isinstance(raw, dict):
        raise GatesConfigError(
            f"Gates policy must be a mapping at {path}. {_DOC_HINT}"
        )

    version_value = raw.get("version")
    try:
        version = int(version_value)
    except (TypeError, ValueError) as exc:
        raise GatesConfigError(
            f"Gates policy requires integer version at {path}. {_DOC_HINT}"
        ) from exc
    if version != 1:
        raise GatesConfigError(
            f"Unsupported gates policy version {version} at {path}. {_DOC_HINT}"
        )

    defaults = raw.get("defaults")
    config_mode: Optional[str] = None
    if isinstance(defaults, dict):
        mode_value = defaults.get("mode")
        if isinstance(mode_value, str):
            config_mode = mode_value.strip().lower()

    mode, mode_source = _resolve_default_mode(config_mode)

    limits_raw = raw.get("limits")
    limits = _parse_limits(limits_raw)

    pre_rules = _parse_rules(raw.get("pre_call"), stage="pre", path=path)
    post_rules = _parse_rules(raw.get("post_call"), stage="post", path=path)

    return GatePolicy(
        path=path,
        version=version,
        default_mode=mode,
        limits=limits,
        pre_rules=pre_rules,
        post_rules=post_rules,
        mode_source=mode_source,
    )


def _read_config(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise GatesConfigError(
            f"Gates policy file not found at {path}. {_DOC_HINT}"
        ) from exc
    except OSError as exc:
        raise GatesConfigError(
            f"Failed to read gates policy at {path}: {exc}. {_DOC_HINT}"
        ) from exc

    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise GatesConfigError(
                f"Failed to parse JSON gates policy at {path}: {exc}. {_DOC_HINT}"
            ) from exc

    if yaml is None:
        raise GatesConfigError(
            "PyYAML is required to load gates.yaml. Install pyyaml or provide JSON."
        )
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:  # pragma: no cover - depends on malformed config
        raise GatesConfigError(
            f"Failed to parse YAML gates policy at {path}: {exc}. {_DOC_HINT}"
        ) from exc


def _resolve_default_mode(config_mode: Optional[str]) -> Tuple[GateAction, str]:
    env_mode = os.environ.get("GATES_MODE")
    if env_mode:
        env_value = env_mode.strip().lower()
        mapped = _map_mode(env_value)
        if mapped is not None:
            return mapped, "env"
    if config_mode:
        mapped = _map_mode(config_mode)
        if mapped is not None:
            return mapped, "config"
    return "allow", "default"


def _map_mode(value: str) -> Optional[GateAction]:
    normalised = value.strip().lower()
    if normalised in {"allow", "warn"}:
        return normalised  # type: ignore[return-value]
    if normalised in {"strict", "deny"}:
        return "deny"
    return None


def _parse_limits(raw: Any) -> Dict[str, int]:
    if not isinstance(raw, Mapping):
        return {}
    limits: Dict[str, int] = {}
    for key in _LIMIT_KEYS:
        value = raw.get(key)
        if value is None:
            continue
        try:
            number = int(float(value))
        except (TypeError, ValueError):
            continue
        if number >= 0:
            limits[key] = int(number)
    return limits


def _parse_rules(
    raw: Any,
    *,
    stage: Literal["pre", "post"],
    path: Path,
) -> Tuple[GateRule, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, Iterable):
        raise GatesConfigError(
            f"Expected a list of {stage} rules in {path}. {_DOC_HINT}"
        )

    rules: list[GateRule] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise GatesConfigError(
                f"Rule #{index} in {stage}_call must be a mapping ({path}). {_DOC_HINT}"
            )
        rule_id = str(item.get("id") or "").strip()
        if not rule_id:
            raise GatesConfigError(
                f"Rule #{index} in {stage}_call is missing an id ({path}). {_DOC_HINT}"
            )

        applies_if = item.get("applies_if")
        reason_map = _normalise_mapping(item.get("reason_code"))
        message_map = _normalise_mapping(item.get("message"))

        deny_spec = _parse_action(
            decision="deny",
            payload=item.get("deny_if"),
            rule_id=rule_id,
            reason_map=reason_map,
            message_map=message_map,
        )
        warn_spec = _parse_action(
            decision="warn",
            payload=item.get("warn_if"),
            rule_id=rule_id,
            reason_map=reason_map,
            message_map=message_map,
        )
        allow_spec = _parse_action(
            decision="allow",
            payload=item.get("allow_if"),
            rule_id=rule_id,
            reason_map=reason_map,
            message_map=message_map,
        )

        rules.append(
            GateRule(
                stage=stage,
                rule_id=rule_id,
                applies_if=applies_if,
                deny=deny_spec,
                warn=warn_spec,
                allow=allow_spec,
            )
        )

    return tuple(rules)


def _normalise_mapping(raw: Any) -> Dict[str, str]:
    if raw is None:
        return {}
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        return {"deny": text}
    if isinstance(raw, Mapping):
        mapping: Dict[str, str] = {}
        for key, value in raw.items():
            if not isinstance(key, str):
                continue
            text_key = key.strip().lower()
            if text_key not in {"allow", "warn", "deny"}:
                continue
            if isinstance(value, str):
                text = value.strip()
                if text:
                    mapping[text_key] = text
        return mapping
    return {}


def _parse_action(
    *,
    decision: GateAction,
    payload: Any,
    rule_id: str,
    reason_map: Mapping[str, str],
    message_map: Mapping[str, str],
) -> Optional[GateActionSpec]:
    if payload is None:
        return None

    reason_default = reason_map.get(decision)
    if not reason_default:
        if decision == "allow":
            reason_default = f"{rule_id}_allow"
        elif decision == "warn":
            reason_default = f"{rule_id}_warn"
        else:
            reason_default = rule_id

    message_default = message_map.get(decision)
    condition: Optional[ConditionSpec] = payload

    if isinstance(payload, Mapping):
        override_reason = payload.get("reason_code")
        if isinstance(override_reason, str):
            text = override_reason.strip()
            if text:
                reason_default = text
        override_message = payload.get("message")
        if isinstance(override_message, str):
            text = override_message.strip()
            if text:
                message_default = text
        if "condition" in payload:
            condition_candidate = payload.get("condition")
            if condition_candidate is None:
                condition = None
            else:
                condition = condition_candidate
        else:
            filtered: Dict[str, Any] = {}
            for key, value in payload.items():
                if key in {"reason_code", "message"}:
                    continue
                filtered[key] = value
            if filtered:
                condition = filtered
            else:
                condition = None

    return GateActionSpec(
        decision=decision,
        condition=condition,
        reason_code=reason_default,
        message=message_default,
    )


def _evaluate_condition(
    spec: ConditionSpec,
    *,
    context: Mapping[str, Any],
    text: str,
) -> bool:
    if spec is None:
        return True
    if isinstance(spec, bool):
        return spec
    if isinstance(spec, (int, float)):
        return bool(spec)
    if isinstance(spec, str):
        return bool(spec.strip())
    if isinstance(spec, Iterable) and not isinstance(spec, Mapping):
        items = list(spec)
        if not items:
            return False
        return all(
            _evaluate_condition(item, context=context, text=text)
            for item in items
        )
    if not isinstance(spec, Mapping):
        return False

    if "all" in spec:
        items = spec.get("all")
        if not isinstance(items, Iterable):
            return False
        return all(
            _evaluate_condition(item, context=context, text=text)
            for item in items
        )

    if "any" in spec:
        items = spec.get("any")
        if not isinstance(items, Iterable):
            return False
        return any(
            _evaluate_condition(item, context=context, text=text)
            for item in items
        )

    if "not" in spec:
        return not _evaluate_condition(spec.get("not"), context=context, text=text)

    if "field" in spec or any(
        key in spec for key in ("value", "value_from", "context", "one_of")
    ):
        field_name = str(spec.get("field") or "").strip()
        value = _resolve_context_value(context, field_name) if field_name else None
        op = str(spec.get("op") or "==").strip().lower()
        if "value_from" in spec:
            expected = _resolve_context_value(context, spec.get("value_from"))
        elif "context" in spec:
            expected = _resolve_context_value(context, spec.get("context"))
        elif "one_of" in spec:
            expected = spec.get("one_of")
        else:
            expected = spec.get("value")
        if expected is None and isinstance(spec.get("value"), Iterable) and not isinstance(
            spec.get("value"), (str, bytes, Mapping)
        ):
            expected = spec.get("value")
        return _compare(value, op, expected)

    if "text_contains" in spec:
        return _text_contains(spec.get("text_contains"), text)

    if "text_not_contains" in spec:
        return not _text_contains(spec.get("text_not_contains"), text)

    if "text_regex" in spec or "regex" in spec:
        pattern = spec.get("text_regex") or spec.get("regex")
        return _text_regex(pattern, text)

    simple_items = [
        (key, value)
        for key, value in spec.items()
        if key
        not in {
            "all",
            "any",
            "not",
            "field",
            "op",
            "value",
            "value_from",
            "context",
            "text_contains",
            "text_not_contains",
            "text_regex",
            "regex",
            "reason_code",
            "message",
            "condition",
            "one_of",
        }
    ]
    if simple_items:
        return all(
            _evaluate_condition(
                {
                    "field": key,
                    "value": value,
                }
                if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping))
                else {"field": key, "op": "in", "value": value},
                context=context,
                text=text,
            )
            for key, value in simple_items
        )

    return False


def _resolve_context_value(context: Mapping[str, Any], key: Any) -> Any:
    if key is None:
        return None
    if isinstance(key, (int, float)):
        return key
    if not isinstance(key, str):
        return None
    path = key.strip()
    if not path:
        return None
    parts = path.split(".")
    current: Any = context
    for part in parts:
        if isinstance(current, Mapping):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
        if current is None:
            return None
    return current


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
    except (TypeError, ValueError):
        return False

    if op in {"!=", "ne"}:
        return value != expected
    if op in {"in", "one_of"}:
        if expected is None:
            return False
        if isinstance(expected, (str, bytes)):
            return str(value) in str(expected)
        try:
            return value in expected  # type: ignore[operator]
        except TypeError:
            return False
    if op in {"contains"}:
        if value is None:
            return False
        if isinstance(value, (str, bytes)):
            if expected is None:
                return False
            if isinstance(expected, (list, tuple, set)):
                return any(str(item) in value for item in expected)
            return str(expected) in value
        try:
            if isinstance(expected, (list, tuple, set)):
                return any(item in value for item in expected)  # type: ignore[operator]
            return expected in value  # type: ignore[operator]
        except TypeError:
            return False
    if op in {"not_in"}:
        if expected is None:
            return True
        try:
            return value not in expected  # type: ignore[operator]
        except TypeError:
            return False
    if op in {"exists"}:
        return value is not None
    return value == expected


def _text_contains(spec: Any, text: str) -> bool:
    haystack = text or ""
    lowered = haystack.lower()
    if isinstance(spec, str):
        needle = spec.strip().lower()
        return bool(needle) and needle in lowered
    if isinstance(spec, Mapping):
        any_tokens = spec.get("any")
        if isinstance(any_tokens, Iterable) and not isinstance(any_tokens, (str, bytes)):
            if any(_string_in(lowered, token) for token in any_tokens):
                return True
        all_tokens = spec.get("all")
        if isinstance(all_tokens, Iterable) and not isinstance(all_tokens, (str, bytes)):
            tokens = list(all_tokens)
            if tokens and all(_string_in(lowered, token) for token in tokens):
                return True
        none_tokens = spec.get("none")
        if isinstance(none_tokens, Iterable) and not isinstance(none_tokens, (str, bytes)):
            tokens = list(none_tokens)
            if tokens and not any(_string_in(lowered, token) for token in tokens):
                return True
        return False
    if isinstance(spec, Iterable):
        return any(_string_in(lowered, token) for token in spec)
    return False


def _text_regex(pattern: Any, text: str) -> bool:
    if not isinstance(pattern, str):
        return False
    try:
        compiled = re.compile(pattern, flags=re.IGNORECASE)
    except re.error:
        return False
    return compiled.search(text or "") is not None


def _string_in(haystack: str, needle: Any) -> bool:
    if isinstance(needle, str):
        token = needle.strip().lower()
    else:
        token = str(needle).strip().lower()
    if not token:
        return False
    return token in haystack


__all__ = [
    "GateDecision",
    "GateEngine",
    "GatesConfigError",
    "get_policy_id",
    "load_gates",
    "post_call_guard",
    "pre_call_guard",
    "reset_cache",
]

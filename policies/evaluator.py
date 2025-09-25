from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml


class EvaluatorConfigError(RuntimeError):
    """Raised when evaluator configuration is invalid."""


@dataclass
class EvaluatorRule:
    rule_id: str
    applies_if: Dict[str, Any]
    success_if: Dict[str, Any]

    def matches(self, context: Dict[str, Any]) -> bool:
        for field, expected in self.applies_if.items():
            actual = context.get(field)
            if isinstance(expected, list):
                expected_values = {self._normalise_value(item) for item in expected}
                if self._normalise_value(actual) not in expected_values:
                    return False
            else:
                if self._normalise_value(actual) != self._normalise_value(expected):
                    return False
        return True

    @staticmethod
    def _normalise_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip().lower()
        return str(value).strip().lower()

    def evaluate(self, *, output_text: str) -> tuple[bool, Optional[str]]:
        checks = {
            "contains_any": self._check_contains_any,
            "forbids_any": self._check_forbids_any,
            "denies_if_amount_gt": self._check_denies_if_amount_gt,
        }
        for key in self.success_if:
            if key not in checks:
                raise EvaluatorConfigError(
                    f"Rule '{self.rule_id}' uses unsupported success_if key '{key}'"
                )
        text = output_text or ""
        for key, handler in checks.items():
            if key not in self.success_if:
                continue
            ok, reason = handler(self.success_if[key], text)
            if not ok:
                return False, reason
        return True, None

    def _check_contains_any(self, requirement: Any, text: str) -> tuple[bool, Optional[str]]:
        patterns = _coerce_string_list(
            requirement,
            field=f"contains_any for rule {self.rule_id}",
            lower=False,
        )
        for pattern in patterns:
            if _pattern_matches(pattern, text, rule_id=self.rule_id):
                return True, None
        pretty = ", ".join(sorted(patterns))
        return False, f"missing required phrase ({pretty})"

    def _check_forbids_any(self, requirement: Any, text: str) -> tuple[bool, Optional[str]]:
        patterns = _coerce_string_list(
            requirement,
            field=f"forbids_any for rule {self.rule_id}",
            lower=False,
        )
        for pattern in patterns:
            if _pattern_matches(pattern, text, rule_id=self.rule_id):
                return False, _forbidden_reason(self.rule_id, pattern)
        return True, None

    def _check_denies_if_amount_gt(self, requirement: Any, text: str) -> tuple[bool, Optional[str]]:
        config = _coerce_amount_rule(requirement, rule_id=self.rule_id)
        amount = _first_amount(text)
        if amount is None:
            return True, None
        limit = config.get("limit")
        if limit is not None and amount > limit:
            reason = config.get("limit_reason") or f"issued > limit (${limit})"
            return False, reason
        threshold = config.get("approval_threshold")
        if threshold is not None and amount > threshold:
            terms = config.get("approval_terms", [])
            if terms and not _text_contains_any(text, terms):
                reason = config.get("approval_reason") or "missing approval for high refund"
                return False, reason
        return True, None


def _text_contains_any(text: str, terms: Iterable[str]) -> bool:
    lowered = text.lower()
    for term in terms:
        if term.strip().lower() in lowered:
            return True
    return False


_FORBIDDEN_REASON_OVERRIDES = {
    "LEAK_REGEX": "LEAK_REGEX",
}


def _pattern_matches(pattern: str, text: str, *, rule_id: str) -> bool:
    try:
        compiled = re.compile(pattern, flags=re.IGNORECASE)
    except re.error as exc:
        raise EvaluatorConfigError(
            f"Rule '{rule_id}' has invalid regex pattern '{pattern}': {exc}"
        ) from exc
    return bool(compiled.search(text))


def _forbidden_reason(rule_id: str, pattern: str) -> str:
    override = _FORBIDDEN_REASON_OVERRIDES.get(rule_id)
    if override:
        return override
    return f"forbidden phrase detected ({pattern})"


def _first_amount(text: str) -> Optional[int]:
    matches = re.findall(r"\$?\s*(\d{1,6})", text)
    if not matches:
        return None
    try:
        return int(matches[0])
    except (TypeError, ValueError):
        return None


def _coerce_string_list(value: Any, *, field: str, lower: bool = True) -> List[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, (list, tuple)):
        items = [str(item) for item in value if str(item).strip()]
    else:
        raise EvaluatorConfigError(f"{field} must be a string or list of strings")
    normalized: List[str] = []
    for item in items:
        stripped = item.strip()
        if not stripped:
            continue
        normalized.append(stripped.lower() if lower else stripped)
    if not normalized:
        raise EvaluatorConfigError(f"{field} must contain at least one entry")
    return normalized


def _coerce_amount_rule(value: Any, *, rule_id: str) -> Dict[str, Any]:
    if isinstance(value, (int, float)):
        return {"limit": int(value)}
    if not isinstance(value, dict):
        raise EvaluatorConfigError(
            f"denies_if_amount_gt for rule '{rule_id}' must be a mapping or integer"
        )
    allowed_keys = {
        "limit",
        "approval_threshold",
        "approval_terms",
        "approval_reason",
        "limit_reason",
    }
    for key in value:
        if key not in allowed_keys:
            raise EvaluatorConfigError(
                f"Rule '{rule_id}' has unsupported denies_if_amount_gt key '{key}'"
            )
    payload: Dict[str, Any] = {}
    if "limit" in value:
        payload["limit"] = int(value["limit"])
    if "approval_threshold" in value:
        payload["approval_threshold"] = int(value["approval_threshold"])
    if "approval_terms" in value:
        payload["approval_terms"] = _coerce_string_list(
            value["approval_terms"], field=f"approval_terms for rule {rule_id}"
        )
    if "approval_reason" in value:
        payload["approval_reason"] = str(value["approval_reason"]).strip()
    if "limit_reason" in value:
        payload["limit_reason"] = str(value["limit_reason"]).strip()
    return payload


class Evaluator:
    def __init__(self, *, version: str, rules: List[EvaluatorRule]) -> None:
        self.version = version
        self.rules = rules

    @classmethod
    def from_path(cls, path: Path) -> "Evaluator":
        if not path.exists():
            raise FileNotFoundError(
                f"Evaluator rules not found at {path}. Provide --evaluator to specify an alternate file."
            )
        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - filesystem errors
            raise EvaluatorConfigError(f"Failed to read evaluator config {path}: {exc}")
        try:
            data = yaml.safe_load(raw_text) or {}
        except yaml.YAMLError as exc:
            raise EvaluatorConfigError(f"Invalid YAML in evaluator config {path}: {exc}")
        if not isinstance(data, dict):
            raise EvaluatorConfigError("Evaluator config must be a mapping")
        version = data.get("version")
        if version is None:
            raise EvaluatorConfigError("Evaluator config missing required 'version'")
        version_text = str(version)
        rules_raw = data.get("rules")
        if not isinstance(rules_raw, list) or not rules_raw:
            raise EvaluatorConfigError("Evaluator config requires a non-empty 'rules' list")
        rules: List[EvaluatorRule] = []
        for entry in rules_raw:
            if not isinstance(entry, dict):
                raise EvaluatorConfigError("Each rule must be a mapping")
            allowed_keys = {"id", "applies_if", "success_if"}
            for key in entry:
                if key not in allowed_keys:
                    raise EvaluatorConfigError(
                        f"Rule entry has unsupported key '{key}'"
                    )
            rule_id = str(entry.get("id") or "").strip()
            if not rule_id:
                raise EvaluatorConfigError("Rule missing required 'id'")
            applies_if = entry.get("applies_if")
            if not isinstance(applies_if, dict) or not applies_if:
                raise EvaluatorConfigError(
                    f"Rule '{rule_id}' missing non-empty applies_if mapping"
                )
            success_if = entry.get("success_if")
            if not isinstance(success_if, dict) or not success_if:
                raise EvaluatorConfigError(
                    f"Rule '{rule_id}' missing non-empty success_if mapping"
                )
            rules.append(
                EvaluatorRule(
                    rule_id=rule_id,
                    applies_if=dict(applies_if),
                    success_if=dict(success_if),
                )
            )
        return cls(version=version_text, rules=rules)

    def _matching_rules(self, context: Dict[str, Any]) -> List[EvaluatorRule]:
        matches = [rule for rule in self.rules if rule.matches(context)]
        if not matches:
            raise EvaluatorConfigError(
                "No evaluator rule matched the provided context; update policies/evaluator.yaml"
            )
        return matches

    def select_rule(self, context: Dict[str, Any]) -> EvaluatorRule:
        return self._matching_rules(context)[0]

    def evaluate(
        self, *, context: Dict[str, Any], output_text: str
    ) -> tuple[str, bool, Optional[str]]:
        matches = self._matching_rules(context)
        final_rule_id = matches[-1].rule_id
        final_reason: Optional[str] = None
        for rule in matches:
            ok, reason = rule.evaluate(output_text=output_text)
            if not ok:
                return rule.rule_id, False, reason
            final_rule_id = rule.rule_id
            final_reason = reason
        return final_rule_id, True, final_reason


def load_evaluator(path: Path | str) -> Evaluator:
    return Evaluator.from_path(Path(path))

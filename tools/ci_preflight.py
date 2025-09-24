#!/usr/bin/env python3
"""Validate configuration files before CI workflows run."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Mapping, MutableMapping, Sequence, Tuple


try:  # pragma: no cover - import guard for local executions without deps
    import yaml
except Exception as exc:  # noqa: BLE001 - surface the original exception text
    print(f"ERROR tools/ci_preflight.py requires PyYAML: {exc}")
    sys.exit(1)

try:  # pragma: no cover - import guard for local executions without deps
    from jsonschema import Draft202012Validator, exceptions as jsonschema_exceptions
except Exception as exc:  # noqa: BLE001 - surface the original exception text
    print(f"ERROR tools/ci_preflight.py requires jsonschema: {exc}")
    sys.exit(1)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


@dataclass(frozen=True)
class ConfigSpec:
    """Configuration document wired into preflight validation."""

    relative_path: str
    schema_filename: str

    @property
    def path(self) -> Path:
        return REPO_ROOT / self.relative_path

    @property
    def schema_path(self) -> Path:
        return REPO_ROOT / self.schema_filename


@dataclass(frozen=True)
class Violation:
    path: Tuple[object, ...]
    message: str


CONFIG_SPECS: Tuple[ConfigSpec, ...] = (
    ConfigSpec("thresholds.yaml", "schemas/thresholds.schema.json"),
    ConfigSpec("specs/threat_model.yaml", "schemas/threat_model.schema.json"),
    ConfigSpec("policies/evaluator.yaml", "schemas/evaluator.schema.json"),
    ConfigSpec("policies/gates.yaml", "schemas/gates.schema.json"),
)

REAL_REQUIRED: Tuple[str, ...] = (
    "thresholds.yaml",
    "policies/evaluator.yaml",
)


def load_schema(path: Path) -> Draft202012Validator:
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:  # pragma: no cover - schema missing is fatal
        raise SystemExit(f"ERROR schema file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR invalid JSON schema at {path}: {exc}") from exc
    try:
        return Draft202012Validator(schema)
    except jsonschema_exceptions.SchemaError as exc:  # pragma: no cover - developer error
        raise SystemExit(f"ERROR schema at {path} is invalid: {exc}") from exc


def detect_context() -> str:
    override = os.getenv("CI_PREFLIGHT_MODE")
    if override:
        text = override.strip().lower()
        if text in {"real", "strict"}:
            return "real"
        if text in {"pr", "dry-run", "dryrun"}:
            return "pr"
        return text

    event = os.getenv("GITHUB_EVENT_NAME", "").strip().lower()
    if event == "pull_request":
        return "pr"
    if event == "workflow_dispatch":
        return "workflow_dispatch"
    if event == "push":
        ref = os.getenv("GITHUB_REF", "").strip().lower()
        if ref == "refs/heads/main":
            return "main"
        return "push"
    return "local"


def required_files(context: str) -> Tuple[str, ...]:
    override = os.getenv("CI_PREFLIGHT_REQUIRED")
    if override:
        tokens = [token.strip() for token in re.split(r"[,\s]+", override) if token.strip()]
        return tuple(tokens)

    if context in {"real", "workflow_dispatch", "main"}:
        return REAL_REQUIRED
    return tuple()


def load_yaml_document(path: Path) -> object:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise RuntimeError(f"failed to read file: {exc}") from exc

    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RuntimeError(f"invalid YAML: {exc}") from exc


def describe_error(error: jsonschema_exceptions.ValidationError) -> Tuple[Tuple[object, ...], str]:
    path_parts: List[object] = list(error.absolute_path)
    validator = error.validator
    value = error.validator_value
    instance = error.instance

    if validator == "required":
        missing = _extract_quoted_token(error.message)
        if missing:
            path_parts.append(missing)
        return tuple(path_parts), f"missing required property '{missing or ''}'".rstrip()

    if validator == "additionalProperties":
        unexpected = _extract_quoted_token(error.message)
        if unexpected:
            path_parts.append(unexpected)
        message = unexpected and f"unexpected property '{unexpected}'" or error.message
        return tuple(path_parts), message

    if validator == "type":
        expected = _format_expected_type(value)
        actual = type(instance).__name__
        return tuple(path_parts), f"expected type {expected} (found {actual})"

    if validator == "enum":
        allowed = ", ".join(str(item) for item in value)
        return tuple(path_parts), f"must be one of {{{allowed}}} (found {instance!r})"

    if validator == "const":
        return tuple(path_parts), f"must equal {value!r} (found {instance!r})"

    if validator == "minimum":
        return tuple(path_parts), f"must be >= {value} (found {instance})"

    if validator == "maximum":
        return tuple(path_parts), f"must be <= {value} (found {instance})"

    if validator == "minItems":
        length = len(instance) if hasattr(instance, "__len__") else "unknown"
        return tuple(path_parts), f"must contain at least {value} items (found {length})"

    if validator == "minLength":
        length = len(instance) if isinstance(instance, str) else "unknown"
        return tuple(path_parts), f"must be at least {value} characters (found {length})"

    if validator == "minProperties":
        length = len(instance) if isinstance(instance, MutableMapping) else "unknown"
        return tuple(path_parts), f"must define at least {value} properties (found {length})"

    return tuple(path_parts), error.message


def _format_expected_type(value: object) -> str:
    if isinstance(value, list):
        return " or ".join(sorted(str(item) for item in value))
    return str(value)


def _extract_quoted_token(message: str) -> str | None:
    match = re.search(r"'([^']+)'", message)
    if match:
        return match.group(1)
    return None


def format_path(parts: Sequence[object]) -> str:
    if not parts:
        return "$"
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
            continue
        token = str(part)
        if token.isidentifier():
            path += f".{token}"
        else:
            path += f"[{json.dumps(token)}]"
    return path


def sort_key(error: jsonschema_exceptions.ValidationError) -> Tuple[Tuple[int, str], ...]:
    key: List[Tuple[int, str]] = []
    for part in error.absolute_path:
        if isinstance(part, int):
            key.append((1, f"{part:08d}"))
        else:
            key.append((0, str(part)))
    return tuple(key)


def _check_unique_rule_ids(data: object) -> List[Violation]:
    violations: List[Violation] = []
    if not isinstance(data, Mapping):
        return violations
    rules = data.get("rules")
    if not isinstance(rules, list):
        return violations
    seen: Dict[str, int] = {}
    for idx, entry in enumerate(rules):
        if not isinstance(entry, Mapping):
            continue
        rule_id = entry.get("id")
        if not isinstance(rule_id, str):
            continue
        token = rule_id.strip()
        if not token:
            continue
        if token in seen:
            first_idx = seen[token]
            message = f"duplicate rule id '{token}' (first seen at rules[{first_idx}].id)"
            violations.append(Violation(("rules", idx, "id"), message))
        else:
            seen[token] = idx
    return violations


EXTRA_CHECKS: Mapping[str, Tuple[Callable[[object], List[Violation]], ...]] = {
    "policies/evaluator.yaml": (_check_unique_rule_ids,),
}


def run_extra_checks(spec: ConfigSpec, data: object) -> List[Violation]:
    callbacks = EXTRA_CHECKS.get(spec.relative_path)
    if not callbacks:
        return []
    results: List[Violation] = []
    for callback in callbacks:
        results.extend(callback(data))
    return results


def validate_spec(spec: ConfigSpec, validator: Draft202012Validator, *, required: bool) -> List[Violation]:
    rel_path = spec.relative_path
    path = spec.path
    if not path.exists():
        if required:
            message = "required file not found for REAL runs"
            print(f"ERROR {rel_path} $: {message}")
            return [Violation(tuple(), message)]
        print(f"SKIP {rel_path} not found (skipped)")
        return []

    try:
        data = load_yaml_document(path)
    except FileNotFoundError:
        message = "required file not found"
        print(f"ERROR {rel_path} $: {message}")
        return [Violation(tuple(), message)]
    except RuntimeError as exc:
        text = str(exc)
        print(f"ERROR {rel_path} $: {text}")
        return [Violation(tuple(), text)]

    errors = sorted(validator.iter_errors(data), key=sort_key)
    violations = [Violation(*describe_error(error)) for error in errors]
    violations.extend(run_extra_checks(spec, data))

    if violations:
        for violation in violations:
            print(f"ERROR {rel_path} {format_path(violation.path)}: {violation.message}")
        return violations

    print(f"OK {rel_path}")
    return []


def main() -> int:
    context = detect_context()
    required = set(required_files(context))

    validators = {spec: load_schema(spec.schema_path) for spec in CONFIG_SPECS}

    total_errors = 0
    files_with_errors: Dict[str, int] = {}

    for spec in CONFIG_SPECS:
        violations = validate_spec(
            spec,
            validators[spec],
            required=spec.relative_path in required,
        )
        if not violations:
            continue
        total_errors += len(violations)
        files_with_errors[spec.relative_path] = len(violations)

    if total_errors:
        file_count = len(files_with_errors)
        print(f"PREFLIGHT: FAIL ({total_errors} errors in {file_count} files)")
        return 1

    print("PREFLIGHT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())


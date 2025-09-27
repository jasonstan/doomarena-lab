#!/usr/bin/env python3
"""Evaluate aggregated run metrics against repo thresholds."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

try:
    from tools.constants import (
        PLACEHOLDER_INPUT_VALUES,
        PLACEHOLDER_OUTPUT_VALUES,
    )
except ModuleNotFoundError:  # pragma: no cover
    from constants import (  # type: ignore
        PLACEHOLDER_INPUT_VALUES,
        PLACEHOLDER_OUTPUT_VALUES,
    )

try:
    from tools.report_utils import normalize_literal
except ModuleNotFoundError:  # pragma: no cover
    from report_utils import normalize_literal  # type: ignore

import yaml

REPORT_JSON_NAME = "run_report.json"
WARN_EXIT_CODE = 78


@dataclass
class Metrics:
    total_trials: int = 0
    callable_trials: int = 0
    passed_trials: int = 0
    post_deny: int = 0

    @property
    def pass_rate(self) -> float:
        if self.callable_trials <= 0:
            return 0.0
        return self.passed_trials / float(self.callable_trials)


@dataclass
class PassRateThreshold:
    warn_below: Optional[float] = None
    fail_below: Optional[float] = None


@dataclass
class ThresholdConfig:
    min_total_trials: Optional[int] = None
    min_callable_trials: Optional[int] = None
    min_pass_rate: Optional[float] = None
    max_post_deny: Optional[int] = None
    policy: str = "warn"
    notes: str = ""
    version: int = 1
    pass_rate_callable: Optional[PassRateThreshold] = None


@dataclass
class EvaluationOutcome:
    status: str
    exit_code: int
    reasons: list[str]
    detail_lines: list[str]
    policy: str
    strict_mode: bool


def _as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return int(text)
        except ValueError:
            try:
                return int(float(text))
            except ValueError:
                return default
    return default


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        text = text.rstrip("%")
        try:
            return float(text)
        except ValueError:
            return default
    return default


def load_thresholds(path: Path) -> Optional[ThresholdConfig]:
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        print(f"ERROR: failed to parse {path}: {exc}", file=sys.stderr)
        return None
    if not data:
        return None
    if not isinstance(data, dict):
        raise ValueError(f"thresholds.yaml must be a mapping, got {type(data).__name__}")

    version = _as_int(data.get("version"), 1) or 1
    if version != 1:
        raise ValueError(f"Unsupported thresholds version: {version}")

    min_total_trials = _as_int(data.get("min_total_trials"))
    min_callable_trials = _as_int(data.get("min_callable_trials"))
    min_pass_rate = _as_float(data.get("min_pass_rate"))
    if min_pass_rate is not None and not (0.0 <= min_pass_rate <= 1.0):
        raise ValueError("min_pass_rate must be between 0 and 1")
    max_post_deny = _as_int(data.get("max_post_deny"))

    pass_rate_callable = None
    raw_pass_rate_callable = data.get("pass_rate_callable")
    if raw_pass_rate_callable is not None:
        if not isinstance(raw_pass_rate_callable, dict):
            raise ValueError("pass_rate_callable must be a mapping")
        warn_below = _as_float(raw_pass_rate_callable.get("warn_below"))
        fail_below = _as_float(raw_pass_rate_callable.get("fail_below"))
        for name, value in (("warn_below", warn_below), ("fail_below", fail_below)):
            if value is not None and not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be between 0 and 1")
        if (
            warn_below is not None
            and fail_below is not None
            and warn_below < fail_below
        ):
            raise ValueError("warn_below must be >= fail_below when both are provided")
        pass_rate_callable = PassRateThreshold(
            warn_below=warn_below,
            fail_below=fail_below,
        )

    policy_raw = str(data.get("policy", "warn") or "warn").strip().lower()
    if policy_raw not in {"allow", "warn", "strict"}:
        raise ValueError(f"Invalid policy value: {policy_raw}")

    notes = str(data.get("notes") or "").strip()

    return ThresholdConfig(
        min_total_trials=min_total_trials,
        min_callable_trials=min_callable_trials,
        min_pass_rate=min_pass_rate,
        max_post_deny=max_post_deny,
        pass_rate_callable=pass_rate_callable,
        policy=policy_raw,
        notes=notes,
        version=version,
    )


def _read_run_report(run_dir: Path) -> Optional[dict[str, Any]]:
    report_path = run_dir / REPORT_JSON_NAME
    if not report_path.exists():
        return None
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _metrics_from_report(payload: dict[str, Any]) -> Metrics:
    total = _as_int(payload.get("total_trials"), 0) or 0
    callable_trials = _as_int(
        payload.get("called_trials"),
        _as_int(payload.get("callable_trials"), 0) or 0,
    ) or 0
    passed = _as_int(payload.get("passed_trials"), 0) or 0
    post_deny = _as_int(payload.get("post_deny"), 0) or 0
    return Metrics(
        total_trials=total,
        callable_trials=callable_trials,
        passed_trials=passed,
        post_deny=post_deny,
    )


def _metrics_from_summary(summary_path: Path) -> Metrics:
    if not summary_path.exists():
        return Metrics()
    try:
        with summary_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            total_trials = 0
            callable_trials = 0
            passed_trials = 0
            post_deny_total = 0
            found_row = False
            for row in reader:
                if not row:
                    continue

                total = _as_int(row.get("total_trials"))
                if total is None:
                    total = _as_int(row.get("trials"), 0)

                callable_value = _as_int(row.get("called_trials"))
                if callable_value is None:
                    callable_value = _as_int(row.get("callable"), 0)

                passed = _as_int(row.get("success"))
                if passed is None:
                    passed = _as_int(row.get("successes"), 0)

                post_deny_value = _as_int(row.get("post_deny"))
                if post_deny_value is None:
                    post_deny_value = 0

                if (
                    total is None
                    and callable_value is None
                    and passed is None
                    and post_deny_value == 0
                ):
                    continue

                found_row = True
                total_trials += total or 0
                callable_trials += callable_value or 0
                passed_trials += passed or 0
                post_deny_total += post_deny_value or 0

            if not found_row:
                return Metrics()

            return Metrics(
                total_trials=total_trials,
                callable_trials=callable_trials,
                passed_trials=passed_trials,
                post_deny=post_deny_total,
            )
    except FileNotFoundError:
        return Metrics()
    return Metrics()


def load_metrics(run_dir: Path) -> Metrics:
    report = _read_run_report(run_dir)
    if report:
        return _metrics_from_report(report)
    summary_path = run_dir / "summary.csv"
    return _metrics_from_summary(summary_path)


def _warn_missing_trial_io(run_dir: Path) -> None:
    rows_path = run_dir / "rows.jsonl"
    if not rows_path.exists():
        return

    callable_rows = 0
    missing_rows = 0

    try:
        with rows_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if payload.get("callable") is not True:
                    continue
                callable_rows += 1
                input_text = normalize_literal(payload.get("input_text"))
                output_text = normalize_literal(payload.get("output_text"))
                input_missing = not input_text or input_text in PLACEHOLDER_INPUT_VALUES
                output_missing = not output_text or output_text in PLACEHOLDER_OUTPUT_VALUES
                if input_missing or output_missing:
                    missing_rows += 1
    except OSError:
        return

    if callable_rows <= 0 or missing_rows <= 0:
        return

    ratio = missing_rows / float(callable_rows)
    if missing_rows >= 5 and ratio >= 0.6:
        print(
            "WARNING: missing literal trial I/O for "
            f"{missing_rows}/{callable_rows} callable rows in {rows_path} — "
            "check runner input_text/output_text persistence."
        )


def evaluate_thresholds(
    metrics: Metrics,
    thresholds: Optional[ThresholdConfig],
    strict_override: bool = False,
) -> EvaluationOutcome:
    policy = thresholds.policy if thresholds else "warn"
    notes = thresholds.notes if thresholds else ""
    strict_mode = strict_override or policy == "strict"

    reasons: list[str] = []
    detail_lines: list[str] = []

    fail_detected = False
    checks_met: list[bool] = []

    def add_detail(line: str) -> None:
        detail_lines.append(line)

    def check_min(
        label: str,
        value: float,
        threshold_value: Optional[float],
        reason_builder,
        fmt_value,
        fmt_threshold,
        suffix: str = "",
    ) -> None:
        if threshold_value is None:
            add_detail(f"- {label}: {fmt_value(value)} (no minimum){suffix}")
            checks_met.append(True)
            return
        met = value >= threshold_value
        status = "OK" if met else "MISS"
        add_detail(
            f"- {label}: {fmt_value(value)} (min {fmt_threshold(threshold_value)}) [{status}]{suffix}"
        )
        if not met:
            reasons.append(reason_builder(value, threshold_value))
        checks_met.append(met)

    def check_max(
        label: str,
        value: float,
        threshold_value: Optional[float],
        reason_builder,
        fmt_value,
        fmt_threshold,
    ) -> None:
        if threshold_value is None:
            add_detail(f"- {label}: {fmt_value(value)} (no maximum)")
            checks_met.append(True)
            return
        met = value <= threshold_value
        status = "OK" if met else "MISS"
        add_detail(
            f"- {label}: {fmt_value(value)} (max {fmt_threshold(threshold_value)}) [{status}]"
        )
        if not met:
            reasons.append(reason_builder(value, threshold_value))
        checks_met.append(met)

    # total trials
    check_min(
        "total_trials",
        metrics.total_trials,
        thresholds.min_total_trials if thresholds else None,
        lambda value, threshold: f"total={int(value)} < min_total={int(threshold)}",
        lambda value: str(int(value)),
        lambda value: str(int(value)),
    )

    # callable trials
    check_min(
        "callable_trials",
        metrics.callable_trials,
        thresholds.min_callable_trials if thresholds else None,
        lambda value, threshold: f"callable={int(value)} < min_callable={int(threshold)}",
        lambda value: str(int(value)),
        lambda value: str(int(value)),
    )

    # pass rate
    ratio_suffix = ""
    if metrics.callable_trials > 0:
        ratio_suffix = f" ({metrics.passed_trials}/{metrics.callable_trials})"
    else:
        ratio_suffix = f" ({metrics.passed_trials}/0)"

    if thresholds and thresholds.pass_rate_callable:
        warn_threshold = thresholds.pass_rate_callable.warn_below
        fail_threshold = thresholds.pass_rate_callable.fail_below
        baseline = thresholds.min_pass_rate if thresholds else None
        if warn_threshold is None:
            warn_threshold = baseline
        if fail_threshold is None:
            fail_threshold = baseline

        pass_rate_value = metrics.pass_rate
        status_tag = "OK"
        reason_text: Optional[str] = None

        if fail_threshold is not None and pass_rate_value < fail_threshold:
            status_tag = "FAIL"
            reason_text = (
                f"pass_rate={pass_rate_value:.2f} < fail_below={fail_threshold:.2f}"
            )
            fail_detected = True
        elif warn_threshold is not None and pass_rate_value < warn_threshold:
            status_tag = "WARN"
            reason_text = (
                f"pass_rate={pass_rate_value:.2f} < warn_below={warn_threshold:.2f}"
            )

        thresholds_parts: list[str] = []
        thresholds_parts.append(
            warn_threshold is not None and f"warn {warn_threshold:.2f}" or "warn n/a"
        )
        thresholds_parts.append(
            fail_threshold is not None and f"fail {fail_threshold:.2f}" or "fail n/a"
        )
        thresholds_text = "; ".join(thresholds_parts)

        add_detail(
            f"- pass_rate: {pass_rate_value:.2f}{ratio_suffix} ({thresholds_text}) [{status_tag}]"
        )
        if reason_text:
            reasons.append(reason_text)
        checks_met.append(status_tag == "OK")
    else:
        check_min(
            "pass_rate",
            metrics.pass_rate,
            thresholds.min_pass_rate if thresholds else None,
            lambda value, threshold: f"pass_rate={value:.2f} < min={threshold:.2f}",
            lambda value: f"{value:.2f}",
            lambda value: f"{value:.2f}",
            suffix=ratio_suffix,
        )

    # post deny counts
    check_max(
        "post_deny",
        metrics.post_deny,
        thresholds.max_post_deny if thresholds else None,
        lambda value, threshold: f"post_deny={int(value)} > max_post_deny={int(threshold)}",
        lambda value: str(int(value)),
        lambda value: str(int(value)),
    )

    all_met = all(checks_met) if checks_met else True

    if fail_detected:
        status = "FAIL"
        exit_code = 1
    elif all_met or not reasons:
        status = "OK"
        exit_code = 0
    else:
        if strict_mode:
            status = "FAIL"
            exit_code = 1
        else:
            if policy == "allow":
                status = "OK"
                exit_code = 0
            elif policy == "warn":
                status = "WARN"
                exit_code = WARN_EXIT_CODE
            else:  # policy == "strict"
                status = "FAIL"
                exit_code = 1

    if notes:
        detail_lines.append(f"- notes: {notes}")

    return EvaluationOutcome(
        status=status,
        exit_code=exit_code,
        reasons=reasons,
        detail_lines=detail_lines,
        policy=policy,
        strict_mode=strict_mode,
    )


def _resolve_run_dir(results_root: Path, run_id: Optional[str]) -> tuple[Path, Optional[str]]:
    if run_id:
        return results_root / run_id, run_id

    env_run_id = os.environ.get("RUN_ID", "").strip()
    if env_run_id:
        return results_root / env_run_id, env_run_id

    marker = results_root / ".run_id"
    if marker.exists():
        marker_run = marker.read_text(encoding="utf-8").strip()
        if marker_run:
            return results_root / marker_run, marker_run

    latest = results_root / "LATEST"
    if latest.exists():
        try:
            resolved = latest.resolve(strict=False)
        except Exception:
            resolved = latest
        return resolved, resolved.name

    pointer = results_root / "LATEST.path"
    if pointer.exists():
        target_text = pointer.read_text(encoding="utf-8").strip()
        if target_text:
            target = Path(target_text)
            return target, target.name

    return results_root, None


def build_summary_line(
    outcome: EvaluationOutcome,
    metrics: Metrics,
) -> str:
    if outcome.reasons:
        reasons_text = "; ".join(outcome.reasons)
        if outcome.status == "OK" and outcome.policy == "allow":
            return f"THRESHOLDS: OK (policy=allow; {reasons_text})"
        return f"THRESHOLDS: {outcome.status} ({reasons_text})"

    parts = [
        f"total={metrics.total_trials}",
        f"callable={metrics.callable_trials}",
        f"pass={metrics.passed_trials}",
    ]
    pass_rate_text = f"pass_rate={metrics.pass_rate:.2f}"
    parts.append(f"⇒ {pass_rate_text}")
    if outcome.policy == "allow" and outcome.status == "OK":
        parts.append("(policy=allow)")
    return f"THRESHOLDS: {outcome.status} (" + ", ".join(parts) + ")"


def _shorten_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def build_detail_block(
    outcome: EvaluationOutcome,
    run_dir: Path,
    run_id: Optional[str],
) -> list[str]:
    details = []
    run_label = run_id if run_id else "n/a"
    dir_display = _shorten_path(run_dir)
    details.append(
        f"- run: {run_label} · dir={dir_display} · policy={outcome.policy} · strict={'1' if outcome.strict_mode else '0'}"
    )
    details.extend(outcome.detail_lines)
    return details


def update_run_report(
    run_dir: Path,
    summary_line: str,
    outcome: EvaluationOutcome,
    metrics: Metrics,
) -> None:
    report_path = run_dir / REPORT_JSON_NAME
    if not report_path.exists():
        return
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    payload["thresholds"] = {
        "status": outcome.status,
        "exit_code": outcome.exit_code,
        "policy": outcome.policy,
        "strict": bool(outcome.strict_mode),
        "summary": summary_line,
        "reasons": outcome.reasons,
        "metrics": {
            "total_trials": metrics.total_trials,
            "callable_trials": metrics.callable_trials,
            "passed_trials": metrics.passed_trials,
            "pass_rate": metrics.pass_rate,
            "post_deny": metrics.post_deny,
        },
    }
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check run metrics against thresholds")
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run identifier (defaults to results/.run_id or LATEST)",
    )
    parser.add_argument(
        "--results-root",
        default="results",
        help="Directory containing run outputs (default: results)",
    )
    parser.add_argument(
        "--thresholds",
        default="thresholds.yaml",
        help="Path to thresholds YAML file (default: thresholds.yaml)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat violations as failures regardless of policy",
    )
    parser.add_argument(
        "--no-report-update",
        action="store_true",
        help="Do not inject threshold status into run_report.json",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    results_root = Path(args.results_root).expanduser()
    run_dir, run_id = _resolve_run_dir(results_root, args.run_id)

    thresholds_path = Path(args.thresholds).expanduser()
    thresholds = load_thresholds(thresholds_path)

    metrics = load_metrics(run_dir)
    _warn_missing_trial_io(run_dir)
    outcome = evaluate_thresholds(metrics, thresholds, strict_override=args.strict)
    summary_line = build_summary_line(outcome, metrics)
    detail_lines = build_detail_block(outcome, run_dir, run_id)

    print(summary_line)
    for line in detail_lines:
        print(line)

    if not args.no_report_update:
        update_run_report(run_dir, summary_line, outcome, metrics)

    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import csv
import json
import argparse
import math
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# NOTE: first step toward de-duplication — leverage shared helpers where useful.
if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent.parent))
from scripts._lib import ensure_dir  # future: read_summary, weighted_asr_by_exp

SUMMARY_COLUMNS: Tuple[str, ...] = (
    "exp_id",
    "exp",
    "config",
    "cfg_hash",
    "mode",
    "seeds",
    "trials",
    "successes",
    "asr",
    "sum_tokens",
    "avg_latency_ms",
    "sum_cost_usd",
    "git_commit",
    "run_at",
    "total_trials",
    "pre_denied",
    "called_trials",
    "pass_rate",
    "p50_ms",
    "p95_ms",
    "total_tokens",
    "post_warn",
    "post_deny",
    "top_reason",
    "calls_made",
    "tokens_prompt_sum",
    "tokens_completion_sum",
    "tokens_total_sum",
    "stopped_early",
    "budget_hit",
)


@dataclass
class ExperimentSummary:
    name: str
    trials: int
    weighted_successes: float
    successes: Optional[int]

    @property
    def asr(self) -> float:
        if self.trials <= 0:
            return 0.0
        return self.weighted_successes / float(self.trials)

    @property
    def asr_percent(self) -> float:
        return self.asr * 100.0


def _relative_path(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.name


def _normalise_gate(decision: Any) -> tuple[str, Optional[str], Optional[str]]:
    if not isinstance(decision, dict):
        return "allow", None, None
    value = _stringify(decision.get("decision")).strip().lower()
    if value not in {"allow", "warn", "deny"}:
        value = "allow"
    reason_code = _stringify(decision.get("reason_code")).strip()
    if not reason_code:
        reason_code_opt: Optional[str] = None
    else:
        reason_code_opt = reason_code
    policy_id = _stringify(decision.get("policy_id")).strip()
    if not policy_id:
        policy_id_opt: Optional[str] = None
    else:
        policy_id_opt = policy_id
    return value, reason_code_opt, policy_id_opt


def _increment_gate(counts: Dict[str, int], decision: str) -> None:
    key = decision if decision in {"allow", "warn", "deny"} else "allow"
    counts[key] = int(counts.get(key, 0)) + 1


def _percentile(values: List[float], percentile: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = percentile * float(len(ordered) - 1)
    lower = int(math.floor(rank))
    upper = int(math.ceil(rank))
    if lower == upper:
        return ordered[lower]
    lower_value = ordered[lower]
    upper_value = ordered[upper]
    return lower_value + (upper_value - lower_value) * (rank - lower)


@dataclass
class RunAggregation:
    base_dir: Path
    total_trials: int = 0
    pre_denied: int = 0
    called_trials: int = 0
    passed_trials: int = 0
    post_warn: int = 0
    post_deny: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    cost_present: bool = False
    latencies: List[float] = field(default_factory=list)
    pre_counts: Dict[str, int] = field(
        default_factory=lambda: {"allow": 0, "warn": 0, "deny": 0}
    )
    post_counts: Dict[str, int] = field(
        default_factory=lambda: {"allow": 0, "warn": 0, "deny": 0}
    )
    reason_counts: Counter[str] = field(default_factory=Counter)
    rows_paths: List[str] = field(default_factory=list)
    run_json_paths: List[str] = field(default_factory=list)
    policy_ids: set[str] = field(default_factory=set)
    encountered_rows_file: bool = False
    calls_attempted_count: int = 0
    calls_made_count: int = 0
    prompt_tokens_total: int = 0
    completion_tokens_total: int = 0
    usage_calls_attempted: Optional[int] = None
    usage_calls_made: Optional[int] = None
    usage_tokens_prompt_sum: Optional[int] = None
    usage_tokens_completion_sum: Optional[int] = None
    usage_tokens_total_sum: Optional[int] = None
    budget_stopped_early: Optional[bool] = None
    budget_hit_value: Optional[str] = None

    def update_from_rows(
        self,
        *,
        path: Path,
        rows: Iterable[Dict[str, Any]],
        run_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.encountered_rows_file = True
        rel = _relative_path(path, self.base_dir)
        if rel not in self.rows_paths:
            self.rows_paths.append(rel)
        if run_meta:
            policy = _stringify(run_meta.get("policy_id")).strip()
            if policy:
                self.policy_ids.add(policy)
            usage_meta = run_meta.get("usage")
            if isinstance(usage_meta, dict):
                calls_attempted = _parse_optional_int(usage_meta.get("calls_attempted"))
                if calls_attempted is not None:
                    self.usage_calls_attempted = calls_attempted
                calls_made = _parse_optional_int(usage_meta.get("calls_made"))
                if calls_made is not None:
                    self.usage_calls_made = calls_made
                prompt_sum = _parse_optional_int(usage_meta.get("tokens_prompt_sum"))
                if prompt_sum is not None:
                    self.usage_tokens_prompt_sum = prompt_sum
                completion_sum = _parse_optional_int(usage_meta.get("tokens_completion_sum"))
                if completion_sum is not None:
                    self.usage_tokens_completion_sum = completion_sum
                total_sum = _parse_optional_int(usage_meta.get("tokens_total_sum"))
                if total_sum is not None:
                    self.usage_tokens_total_sum = total_sum
            budget_meta = run_meta.get("budget")
            if isinstance(budget_meta, dict):
                stopped_value = _parse_optional_bool(budget_meta.get("stopped_early"))
                if stopped_value is not None:
                    self.budget_stopped_early = stopped_value
                hit_value = _stringify(budget_meta.get("budget_hit")).strip()
                if hit_value:
                    self.budget_hit_value = hit_value
        for entry in rows:
            self.total_trials += 1
            pre_decision, pre_reason, pre_policy = _normalise_gate(entry.get("pre_call_gate"))
            if pre_policy:
                self.policy_ids.add(pre_policy)
            _increment_gate(self.pre_counts, pre_decision)
            if pre_reason:
                self.reason_counts[pre_reason] += 1
            attempted = pre_decision != "deny"
            fail_reason_value = _stringify(entry.get("fail_reason")).strip()
            fail_reason_key = fail_reason_value.upper()
            skipped_budget = fail_reason_key == "SKIPPED_BUDGET_REACHED"
            is_dry_run = fail_reason_key == "DRY_RUN"
            if not attempted:
                self.pre_denied += 1
            else:
                self.calls_attempted_count += 1
            called = attempted and not skipped_budget and not is_dry_run
            if called:
                self.called_trials += 1
                self.calls_made_count += 1
                if bool(entry.get("success")):
                    self.passed_trials += 1
                latency_value = _parse_optional_float(entry.get("latency_ms"))
                if latency_value is not None:
                    self.latencies.append(latency_value)
                prompt_tokens = _parse_optional_int(entry.get("prompt_tokens")) or 0
                completion_tokens = _parse_optional_int(entry.get("completion_tokens")) or 0
                self.prompt_tokens_total += int(prompt_tokens)
                self.completion_tokens_total += int(completion_tokens)
                total_tokens = _parse_optional_int(entry.get("total_tokens"))
                if total_tokens is None and (prompt_tokens or completion_tokens):
                    total_tokens = prompt_tokens + completion_tokens
                if total_tokens is not None:
                    self.total_tokens += int(total_tokens)
                cost_value = _parse_optional_float(entry.get("cost_usd"))
                if cost_value is not None:
                    self.estimated_cost += float(cost_value)
                    self.cost_present = True
                post_decision, post_reason, post_policy = _normalise_gate(
                    entry.get("post_call_gate")
                )
                if post_policy:
                    self.policy_ids.add(post_policy)
                _increment_gate(self.post_counts, post_decision)
                if post_reason:
                    self.reason_counts[post_reason] += 1
                if post_decision == "warn":
                    self.post_warn += 1
                elif post_decision == "deny":
                    self.post_deny += 1
            else:
                post_decision, post_reason, post_policy = _normalise_gate(
                    entry.get("post_call_gate")
                )
                if post_policy:
                    self.policy_ids.add(post_policy)
                if post_reason:
                    self.reason_counts[post_reason] += 1

    def register_run_json_path(self, path: Path) -> None:
        if not path.exists():
            return
        rel = _relative_path(path, self.base_dir)
        if rel not in self.run_json_paths:
            self.run_json_paths.append(rel)

    def latency_percentiles(self) -> tuple[Optional[int], Optional[int]]:
        if not self.latencies:
            return None, None
        p50 = _percentile(self.latencies, 0.5)
        p95 = _percentile(self.latencies, 0.95)
        return (
            int(round(p50)) if p50 is not None else None,
            int(round(p95)) if p95 is not None else None,
        )

    def pass_rate_percent(self) -> float:
        denominator = max(self.called_trials, 1)
        return (self.passed_trials / float(denominator)) * 100.0

    def pass_rate_display(self) -> str:
        return f"{self.pass_rate_percent():.1f}%"

    def top_reason(self) -> str:
        if not self.reason_counts:
            return "-"
        max_count = max(self.reason_counts.values())
        candidates = [
            reason
            for reason, count in self.reason_counts.items()
            if count == max_count
        ]
        if not candidates:
            return "-"
        return sorted(candidates)[0]

    def csv_fields(self) -> Dict[str, str]:
        p50, p95 = self.latency_percentiles()
        calls_made = self.usage_calls_made
        if calls_made is None:
            calls_made = self.calls_made_count
        tokens_prompt_sum = self.usage_tokens_prompt_sum
        if tokens_prompt_sum is None:
            tokens_prompt_sum = self.prompt_tokens_total
        tokens_completion_sum = self.usage_tokens_completion_sum
        if tokens_completion_sum is None:
            tokens_completion_sum = self.completion_tokens_total
        tokens_total_sum = self.usage_tokens_total_sum
        if tokens_total_sum is None:
            tokens_total_sum = self.total_tokens
        budget_hit = _stringify(self.budget_hit_value).strip() or "none"
        stopped_value = self.budget_stopped_early
        if stopped_value is None:
            stopped_value = budget_hit.lower() != "none"
        stopped_text = "true" if stopped_value else "false"
        return {
            "total_trials": str(self.total_trials),
            "pre_denied": str(self.pre_denied),
            "called_trials": str(self.called_trials),
            "pass_rate": self.pass_rate_display(),
            "p50_ms": str(p50) if p50 is not None else "",
            "p95_ms": str(p95) if p95 is not None else "",
            "total_tokens": str(self.total_tokens),
            "post_warn": str(self.post_warn),
            "post_deny": str(self.post_deny),
            "top_reason": self.top_reason(),
            "calls_made": str(calls_made),
            "tokens_prompt_sum": str(tokens_prompt_sum),
            "tokens_completion_sum": str(tokens_completion_sum),
            "tokens_total_sum": str(tokens_total_sum),
            "stopped_early": stopped_text,
            "budget_hit": budget_hit,
        }

    def to_dict(self) -> Dict[str, Any]:
        p50, p95 = self.latency_percentiles()
        calls_attempted = self.usage_calls_attempted
        if calls_attempted is None:
            calls_attempted = self.calls_attempted_count
        calls_made = self.usage_calls_made
        if calls_made is None:
            calls_made = self.calls_made_count
        tokens_prompt_sum = self.usage_tokens_prompt_sum
        if tokens_prompt_sum is None:
            tokens_prompt_sum = self.prompt_tokens_total
        tokens_completion_sum = self.usage_tokens_completion_sum
        if tokens_completion_sum is None:
            tokens_completion_sum = self.completion_tokens_total
        tokens_total_sum = self.usage_tokens_total_sum
        if tokens_total_sum is None:
            tokens_total_sum = self.total_tokens
        budget_hit = _stringify(self.budget_hit_value).strip() or "none"
        stopped_value = self.budget_stopped_early
        if stopped_value is None:
            stopped_value = budget_hit.lower() != "none"
        return {
            "total_trials": self.total_trials,
            "pre_denied": self.pre_denied,
            "called_trials": self.called_trials,
            "passed_trials": self.passed_trials,
            "pass_rate": {
                "percent": self.pass_rate_percent(),
                "display": self.pass_rate_display(),
            },
            "latency_ms": {"p50": p50, "p95": p95},
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost, 4)
            if self.cost_present
            else 0.0,
            "cost_present": self.cost_present,
            "post_warn": self.post_warn,
            "post_deny": self.post_deny,
            "gates": {
                "pre": {key: int(self.pre_counts.get(key, 0)) for key in ("allow", "warn", "deny")},
                "post": {key: int(self.post_counts.get(key, 0)) for key in ("allow", "warn", "deny")},
            },
            "top_reason": self.top_reason(),
            "reason_counts": {
                reason: int(count) for reason, count in self.reason_counts.items()
            },
            "rows_paths": list(self.rows_paths),
            "run_json_paths": list(self.run_json_paths),
            "policy_ids": sorted(self.policy_ids),
            "encountered_rows_file": self.encountered_rows_file,
            "has_row_data": self.total_trials > 0,
            "usage": {
                "trials_total": self.total_trials,
                "calls_attempted": calls_attempted,
                "calls_made": calls_made,
                "tokens_prompt_sum": tokens_prompt_sum,
                "tokens_completion_sum": tokens_completion_sum,
                "tokens_total_sum": tokens_total_sum,
            },
            "budget": {
                "stopped_early": bool(stopped_value),
                "budget_hit": budget_hit,
            },
        }


def read_jsonl(path: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    header: Dict[str, Any] | None = None
    summary: Dict[str, Any] | None = None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            event = payload.get("event")
            if event == "header" and header is None:
                header = payload
            elif event == "summary":
                summary = payload
    if header is None:
        raise RuntimeError(f"Missing header in {path}")
    if summary is None:
        raise RuntimeError(f"Missing summary in {path}")
    return header, summary


def _normalise_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalise_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _parse_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = _stringify(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _parse_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = _stringify(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _parse_optional_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off"}:
            return False
    return None


def read_real_rows(
    path: Path,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)

    run_dir = path.parent
    run_meta_path = run_dir / "run.json"
    run_meta: Dict[str, Any] = {}
    if run_meta_path.exists():
        try:
            with run_meta_path.open("r", encoding="utf-8") as handle:
                meta_payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            meta_payload = None
        if isinstance(meta_payload, dict):
            run_meta = meta_payload

    run_id = _stringify(run_meta.get("run_id")) or run_dir.parent.name
    exp_name = _stringify(run_meta.get("exp"))
    if not exp_name and rows:
        exp_name = _stringify(rows[0].get("exp"))
    if not exp_name:
        exp_name = run_dir.name
    model = _stringify(run_meta.get("model"))
    if not model:
        for row in rows:
            model = _stringify(row.get("model"))
            if model:
                break

    seeds_seen: set[str] = set()
    seeds_ordered: List[str] = []

    def _add_seed(value: Any) -> None:
        text = _stringify(value).strip()
        if not text or text in seeds_seen:
            return
        seeds_seen.add(text)
        seeds_ordered.append(text)

    _add_seed(run_meta.get("seed"))
    seeds_value = run_meta.get("seeds")
    if isinstance(seeds_value, (list, tuple)):
        for item in seeds_value:
            _add_seed(item)
    elif seeds_value is not None:
        _add_seed(seeds_value)

    for row in rows:
        _add_seed(row.get("seed"))

    trials = len(rows)
    successes = sum(1 for row in rows if bool(row.get("success")))

    total_tokens = 0
    latency_values: List[float] = []
    cost_total = 0.0
    cost_present = False

    for row in rows:
        total_opt = _parse_optional_int(row.get("total_tokens"))
        if total_opt is None:
            prompt_opt = _parse_optional_int(row.get("prompt_tokens")) or 0
            completion_opt = _parse_optional_int(row.get("completion_tokens")) or 0
            if prompt_opt or completion_opt:
                total_opt = prompt_opt + completion_opt
        if total_opt is not None:
            total_tokens += int(total_opt)

        latency_opt = _parse_optional_float(row.get("latency_ms"))
        if latency_opt is not None:
            latency_values.append(latency_opt)

        cost_opt = _parse_optional_float(row.get("cost_usd"))
        if cost_opt is not None:
            cost_total += cost_opt
            cost_present = True

    avg_latency: Optional[float] = None
    if latency_values:
        avg_latency = sum(latency_values) / float(len(latency_values))

    run_at = _stringify(run_meta.get("started"))
    if not run_at:
        for row in rows:
            run_at = _stringify(row.get("timestamp"))
            if run_at:
                break

    header: Dict[str, Any] = {
        "event": "header",
        "exp": exp_name,
        "exp_id": f"{exp_name}:{run_id}" if run_id else exp_name,
        "config": _stringify(run_meta.get("config")),
        "cfg_hash": _stringify(run_meta.get("cfg_hash")),
        "mode": _stringify(run_meta.get("mode")) or "REAL",
        "seed": seeds_ordered[0] if seeds_ordered else None,
        "seeds": seeds_ordered or None,
        "model": model,
        "run_at": run_at,
        "git_commit": _stringify(run_meta.get("git_commit")),
    }

    summary: Dict[str, Any] = {
        "event": "summary",
        "trials": trials,
        "successes": successes,
        "asr": (successes / trials) if trials else 0.0,
        "sum_tokens": total_tokens,
        "avg_latency_ms": avg_latency,
        "sum_cost_usd": cost_total if cost_present else None,
        "mode": header["mode"],
    }

    return header, summary, rows, run_meta


def _collect_seeds(header: Dict[str, Any]) -> str:
    seen: set[str] = set()
    ordered: List[str] = []

    def _add(item: Any) -> None:
        text = _stringify(item).strip()
        if not text:
            return
        if text in seen:
            return
        seen.add(text)
        ordered.append(text)

    if "seed" in header:
        _add(header.get("seed"))

    seeds_value = header.get("seeds")
    if isinstance(seeds_value, (list, tuple)):
        for item in seeds_value:
            _add(item)
    elif isinstance(seeds_value, str):
        for chunk in seeds_value.split(","):
            _add(chunk)
    elif seeds_value is not None:
        _add(seeds_value)

    return ",".join(ordered)


def _collect_trial_metrics(path: Path) -> tuple[int, Optional[float], Optional[float]]:
    total_tokens = 0
    latency_total = 0.0
    latency_count = 0
    cost_total = 0.0
    cost_present = False

    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                if payload.get("event") != "trial":
                    continue

                total = _normalise_int(payload.get("total_tokens"))
                if total <= 0:
                    prompt = _normalise_int(payload.get("prompt_tokens"))
                    completion = _normalise_int(payload.get("completion_tokens"))
                    if prompt or completion:
                        total = prompt + completion
                if total > 0:
                    total_tokens += total

                latency_value = _parse_optional_float(payload.get("latency_ms"))
                if latency_value is not None:
                    latency_total += latency_value
                    latency_count += 1

                cost_value = _parse_optional_float(payload.get("cost_usd"))
                if cost_value is not None:
                    cost_total += cost_value
                    cost_present = True
    except OSError:
        return 0, None, None

    avg_latency: Optional[float] = None
    if latency_count > 0:
        avg_latency = latency_total / float(latency_count)

    cost_sum: Optional[float] = cost_total if cost_present else None
    return total_tokens, avg_latency, cost_sum


def _load_meta(path: Path) -> Dict[str, Any] | None:
    candidates = [
        path.with_suffix(".meta.json"),
        path.parent / "meta.json",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            with candidate.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            return data
    return None


def _stringify_seeds(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        parts: List[str] = []
        for item in value:
            text = _stringify(item).strip()
            if text and text not in parts:
                parts.append(text)
        return ",".join(parts)
    if value is None:
        return ""
    return _stringify(value)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def _parse_iso_timestamp(value: str) -> Optional[datetime]:
    text = _stringify(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        text = _stringify(value).strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def build_row(path: Path, header: Dict[str, Any], summary: Dict[str, Any]) -> Dict[str, str]:
    meta = _load_meta(path)

    exp_id = _stringify(header.get("exp_id"))
    if meta and meta.get("exp_id"):
        exp_id = _stringify(meta.get("exp_id"))

    exp = _stringify(header.get("exp"))
    config = _stringify(header.get("config"))
    cfg_hash_value = _stringify(header.get("cfg_hash"))

    mode = _stringify(header.get("mode"))
    if meta and meta.get("mode"):
        mode = _stringify(meta.get("mode"))

    git_commit = _stringify(header.get("git_commit"))
    if not git_commit and meta and meta.get("git_commit"):
        git_commit = _stringify(meta.get("git_commit"))
    elif not git_commit and meta and meta.get("git_sha"):
        git_commit = _stringify(meta.get("git_sha"))

    run_at = _stringify(header.get("run_at"))
    if meta and meta.get("timestamp"):
        run_at = _stringify(meta.get("timestamp"))

    seeds = _collect_seeds(header)
    if meta and meta.get("seeds") is not None:
        seeds = _stringify_seeds(meta.get("seeds"))

    trials = _normalise_int(summary.get("trials"))
    if meta and meta.get("trials") is not None:
        try:
            trials = int(meta.get("trials"))
        except (TypeError, ValueError):
            pass
    successes = _normalise_int(summary.get("successes"))
    if trials > 0 and successes > trials:
        successes = trials
    asr_value = summary.get("asr")
    if asr_value is None and trials:
        asr_value = successes / trials
    asr = _normalise_float(asr_value)
    if asr < 0.0:
        asr = 0.0
    elif asr > 1.0:
        asr = 1.0

    tokens_total, avg_latency, cost_sum = _collect_trial_metrics(path)
    if tokens_total == 0:
        tokens_total = _normalise_int(summary.get("sum_tokens"))
    if avg_latency is None:
        avg_latency = _parse_optional_float(summary.get("avg_latency_ms"))
    if cost_sum is None:
        cost_from_summary = _parse_optional_float(summary.get("sum_cost_usd"))
        if cost_from_summary is not None:
            cost_sum = cost_from_summary

    row = {
        "exp_id": exp_id,
        "exp": exp,
        "config": config,
        "cfg_hash": cfg_hash_value,
        "mode": mode,
        "seeds": seeds,
        "trials": str(trials),
        "successes": str(successes),
        "asr": f"{asr:.6f}",
        "sum_tokens": str(tokens_total),
        "avg_latency_ms": f"{avg_latency:.1f}" if avg_latency is not None else "",
        "sum_cost_usd": f"{cost_sum:.4f}" if cost_sum is not None else "",
        "git_commit": git_commit,
        "run_at": run_at,
    }
    return row


def read_existing(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(SUMMARY_COLUMNS):
            return []
        return [dict(row) for row in reader]


def merge_rows(existing: List[Dict[str, str]], new_rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    combined = list(existing)
    seen_keys = {
        (row.get("exp_id", ""), row.get("run_at", ""))
        for row in combined
    }
    for row in new_rows:
        key = (row.get("exp_id", ""), row.get("run_at", ""))
        if key in seen_keys:
            continue
        combined.append(row)
        seen_keys.add(key)
    combined.sort(key=lambda item: item.get("run_at", ""))
    return combined


def write_summary(path: Path, rows: Iterable[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SUMMARY_COLUMNS))
        writer.writeheader()
        for row in rows:
            payload = {column: row.get(column, "") for column in SUMMARY_COLUMNS}
            writer.writerow(payload)


def write_summary_md(base_dir: Path, rows: List[Dict[str, str]]) -> None:
    md_path = base_dir / "summary.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        md_path.write_text("No results available.\n", encoding="utf-8")
        return

    recent = sorted(rows, key=lambda item: item.get("run_at", ""), reverse=True)[:5]
    lines = [
        "| exp | seeds | mode | ASR | trials | successes | git | run_at |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in recent:
        try:
            asr_display = f"{float(row.get('asr', 0.0)):.2f}"
        except (TypeError, ValueError):
            asr_display = _stringify(row.get("asr"))
        successes = row.get("successes", "")
        trials = row.get("trials", "")
        if asr_display and successes and trials:
            asr_display = f"{asr_display} ({successes}/{trials})"
        git_commit = row.get("git_commit", "")[:8]
        lines.append(
            "| {exp} | {seeds} | {mode} | {asr} | {trials} | {successes} | {git} | {run_at} |".format(
                exp=row.get("exp", ""),
                seeds=row.get("seeds", ""),
                mode=row.get("mode", ""),
                asr=asr_display,
                trials=trials,
                successes=successes,
                git=git_commit,
                run_at=row.get("run_at", ""),
            )
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _collect_seed_tokens(rows: Iterable[Dict[str, str]]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for row in rows:
        seeds_value = row.get("seeds")
        if seeds_value is None:
            continue
        raw = _stringify(seeds_value).replace(";", ",")
        if not raw:
            continue
        for chunk in raw.split(","):
            token = chunk.strip()
            if not token:
                continue
            if token in seen:
                continue
            seen.add(token)
            ordered.append(token)
    return ordered


def summarise_experiments(rows: Iterable[Dict[str, str]]) -> List[ExperimentSummary]:
    aggregates: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        exp_name = _stringify(row.get("exp"))
        exp = exp_name.strip()
        if not exp:
            continue

        trials_value = _parse_optional_int(row.get("trials"))
        if trials_value is None or trials_value <= 0:
            continue

        successes_value = _parse_optional_int(row.get("successes"))
        asr_value = _parse_optional_float(row.get("asr"))

        if successes_value is None and asr_value is None:
            continue

        bucket = aggregates.setdefault(
            exp,
            {
                "trials": 0,
                "weighted_successes": 0.0,
                "successes": 0,
                "has_exact_successes": True,
            },
        )

        bucket["trials"] = int(bucket["trials"]) + int(trials_value)

        if successes_value is not None:
            successes_clamped = max(0, min(int(successes_value), int(trials_value)))
            bucket["weighted_successes"] = float(bucket["weighted_successes"]) + float(successes_clamped)
            bucket["successes"] = int(bucket["successes"]) + successes_clamped
        else:
            asr_clamped = _clamp(asr_value or 0.0, 0.0, 1.0)
            bucket["weighted_successes"] = float(bucket["weighted_successes"]) + (asr_clamped * float(trials_value))
            bucket["has_exact_successes"] = False

    summaries: List[ExperimentSummary] = []
    for exp, payload in aggregates.items():
        trials_total = int(payload["trials"])
        weighted_successes = float(payload["weighted_successes"])
        has_exact_successes = bool(payload.get("has_exact_successes", False))
        if not has_exact_successes:
            successes_total: Optional[int] = None
        else:
            successes_total = int(payload.get("successes", 0))
        summaries.append(
            ExperimentSummary(
                name=exp,
                trials=trials_total,
                weighted_successes=weighted_successes,
                successes=successes_total,
            )
        )

    summaries.sort(key=lambda item: (-item.asr, item.name))
    return summaries


def _compute_overall_asr(experiments: Iterable[ExperimentSummary]) -> Optional[float]:
    total_trials = 0
    weighted = 0.0
    for item in experiments:
        total_trials += item.trials
        weighted += item.weighted_successes
    if total_trials <= 0:
        return None
    return (weighted / float(total_trials)) * 100.0


def _resolve_timestamp(rows: Iterable[Dict[str, str]]) -> str:
    latest: Optional[datetime] = None
    for row in rows:
        candidate = _parse_iso_timestamp(row.get("run_at", ""))
        if candidate is None:
            continue
        if latest is None or candidate > latest:
            latest = candidate
    if latest is None:
        latest = datetime.now(timezone.utc)
    return latest.astimezone().isoformat(timespec="seconds")


def _collect_modes(rows: Iterable[Dict[str, str]]) -> List[str]:
    return _dedupe_preserve_order(row.get("mode", "") for row in rows)


def _collect_git_commits(rows: Iterable[Dict[str, str]]) -> List[str]:
    return _dedupe_preserve_order(row.get("git_commit", "") for row in rows)


def _collect_experiments(rows: Iterable[Dict[str, str]]) -> List[str]:
    return _dedupe_preserve_order(row.get("exp", "") for row in rows)


def write_run_notes(base_dir: Path, rows: List[Dict[str, str]]) -> None:
    notes_path = base_dir / "notes.md"
    notes_path.parent.mkdir(parents=True, exist_ok=True)

    experiments = summarise_experiments(rows)
    timestamp_text = _resolve_timestamp(rows)
    seed_tokens = _collect_seed_tokens(rows)
    mode_tokens = _collect_modes(rows)
    git_commits = _collect_git_commits(rows)
    experiment_names = [item.name for item in experiments]
    if not experiment_names:
        experiment_names = _collect_experiments(rows)

    exp_summary = ", ".join(experiment_names) if experiment_names else "n/a"
    mode_summary = ", ".join(mode_tokens) if mode_tokens else "n/a"
    seed_summary = ", ".join(seed_tokens) if seed_tokens else "n/a"

    run_dir_text = base_dir.resolve().as_posix()
    git_commit = git_commits[0] if git_commits else ""
    git_commit_short = git_commit[:8] if git_commit else "n/a"

    total_trials = sum(item.trials for item in experiments)
    overall_asr = _compute_overall_asr(experiments)

    run_id = base_dir.name or run_dir_text
    header_exp = exp_summary if exp_summary != "n/a" else "<unknown>"
    header_mode = mode_summary if mode_summary != "n/a" else "n/a"

    lines: List[str] = []
    lines.append(f"# Experiment Notes – {header_exp} (mode={header_mode}) – {run_id}")
    lines.append("")
    if experiments:
        lines.append(
            "This run evaluated {count} experiment(s) across {trials} trials "
            "using mode(s) {modes} with seeds {seeds}.".format(
                count=len(experiments),
                trials=total_trials,
                modes=mode_summary,
                seeds=seed_summary,
            )
        )
    else:
        lines.append("No experiment results were found for this run.")
    lines.append("")

    lines.append("## Run metadata")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Timestamp | {timestamp_text} |")
    lines.append(f"| EXP | {exp_summary} |")
    lines.append(f"| MODE | {mode_summary} |")
    lines.append(f"| TRIALS | {total_trials} |")
    lines.append(f"| SEEDS | {seed_summary} |")
    lines.append(f"| RUN_DIR | {run_dir_text} |")
    lines.append(f"| GIT_COMMIT | {git_commit_short} |")
    lines.append("")

    if experiments:
        lines.append("## Results")
        lines.append("")
        lines.append("| Experiment | Trials | Successes | Trial-weighted ASR % |")
        lines.append("| --- | ---: | ---: | ---: |")
        for item in experiments:
            successes_display = str(item.successes) if item.successes is not None else "–"
            lines.append(
                "| {name} | {trials} | {successes} | {asr:.2f} |".format(
                    name=item.name,
                    trials=item.trials,
                    successes=successes_display,
                    asr=item.asr_percent,
                )
            )
        lines.append("")
    else:
        lines.append("## Results")
        lines.append("")
        lines.append("No aggregated results were available.")
        lines.append("")

    if overall_asr is None:
        overall_text = "n/a"
    else:
        overall_text = f"{overall_asr:.2f}%"
    lines.append(f"**Overall trial-weighted ASR:** {overall_text}")
    lines.append("")

    summary_csv = base_dir / "summary.csv"
    summary_svg = base_dir / "summary.svg"
    summary_png = base_dir / "summary.png"

    lines.append("## Artifacts")
    lines.append("")
    if summary_csv.exists():
        lines.append(f"- [summary.csv]({summary_csv.name})")
    else:
        lines.append("- summary.csv (missing)")
    if summary_svg.exists():
        lines.append(f"- [summary.svg]({summary_svg.name})")
    if summary_png.exists():
        lines.append(f"- [summary.png]({summary_png.name})")

    jsonl_paths = sorted(base_dir.rglob("*.jsonl"))
    if jsonl_paths:
        lines.append("- Per-seed logs:")
        for path in jsonl_paths:
            try:
                rel = path.relative_to(base_dir)
            except ValueError:
                rel = path
            rel_text = rel.as_posix()
            lines.append(f"  - [{rel_text}]({rel_text})")
    else:
        lines.append("- No per-seed logs were found.")

    chart_path: Optional[Path] = None
    if summary_svg.exists():
        chart_path = summary_svg
    elif summary_png.exists():
        chart_path = summary_png

    if chart_path is not None:
        lines.append("")
        lines.append(f"![Trial-weighted ASR chart]({chart_path.name})")

    lines.append("")
    notes_path.write_text("\n".join(lines), encoding="utf-8")


def write_run_report(
    base_dir: Path, aggregation: RunAggregation, status: Optional[Dict[str, Any]] = None
) -> None:
    payload = aggregation.to_dict()
    payload["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if status is not None:
        payload["status"] = status
    report_path = base_dir / "run_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate DoomArena run outputs")
    parser.add_argument(
        "--outdir",
        default="results",
        help="Directory to scan for jsonl files and write summaries",
    )
    emit_default = os.environ.get("AGGREGATE_EMIT_STATUS", "always")
    if emit_default not in {"always", "never"}:
        emit_default = "always"
    parser.add_argument(
        "--emit-status",
        choices=["always", "never"],
        default=emit_default,
        help="Whether to print RUN status summary lines (default: always; set to never to suppress)",
    )
    return parser.parse_args()


def _format_gate_counts(counts: Dict[str, int]) -> str:
    allow = int(counts.get("allow", 0))
    warn = int(counts.get("warn", 0))
    deny = int(counts.get("deny", 0))
    return f"{allow}/{warn}/{deny}"


def _status_summary(aggregation: RunAggregation) -> tuple[str, str]:
    if not aggregation.encountered_rows_file or aggregation.total_trials <= 0:
        message = "RUN FAIL: no rows.jsonl produced; see earlier error."
        return "fail", message

    called = aggregation.called_trials
    total = aggregation.total_trials
    if total > 0 and called == 0:
        policy = "unknown"
        if aggregation.policy_ids:
            policy = sorted(aggregation.policy_ids)[0]
        message = (
            f"RUN WARN: all trials pre-denied (policy={policy}); no model calls were made."
        )
        return "warn", message

    pass_rate = aggregation.pass_rate_percent()
    pre_counts = _format_gate_counts(aggregation.pre_counts)
    post_counts = _format_gate_counts(aggregation.post_counts)
    top_reason = aggregation.top_reason()
    message = (
        "RUN OK: called={called} total={total} pass_rate={pass_rate:.1f}% "
        "gates: pre a/w/d={pre_counts}, post a/w/d={post_counts} top_reason={top_reason}".format(
            called=called,
            total=total,
            pass_rate=pass_rate,
            pre_counts=pre_counts,
            post_counts=post_counts,
            top_reason=top_reason,
        )
    )
    return "ok", message


def main() -> int:
    args = parse_args()
    base_dir = Path(args.outdir).expanduser()
    base_dir.mkdir(parents=True, exist_ok=True)
    summary_path = base_dir / "summary.csv"

    jsonl_files = sorted(base_dir.rglob("*.jsonl"))
    empty_reason: Optional[str] = None
    if not jsonl_files:
        # Fallback: search one level up for legacy layouts
        parent_dir = base_dir.parent
        fallback: List[Path] = []
        if parent_dir.exists() and parent_dir != base_dir:
            for candidate in parent_dir.rglob("*.jsonl"):
                try:
                    candidate.relative_to(base_dir)
                except ValueError:
                    fallback.append(candidate)
        jsonl_files = sorted(fallback)
        if not jsonl_files:
            empty_reason = (
                f"No usable rows in summary data — no *.jsonl files found under {base_dir}"
            )
            print(empty_reason)

    new_rows: List[Dict[str, str]] = []
    run_metrics = RunAggregation(base_dir=base_dir)

    for path in jsonl_files:
        try:
            if path.name == "rows.jsonl":
                header, summary, trial_rows, run_meta = read_real_rows(path)
                run_metrics.update_from_rows(path=path, rows=trial_rows, run_meta=run_meta)
                run_metrics.register_run_json_path(path.parent / "run.json")
            else:
                header, summary = read_jsonl(path)
        except RuntimeError as exc:
            print(f"Skipping {path}: {exc}")
            continue
        try:
            row = build_row(path, header, summary)
        except Exception as exc:  # pragma: no cover - defensive fallback
            print(f"Failed to process {path}: {exc}")
            continue
        new_rows.append(row)

    run_metrics.register_run_json_path(base_dir / "run.json")

    existing_rows = read_existing(summary_path)
    combined_rows = merge_rows(existing_rows, new_rows)

    metric_columns = run_metrics.csv_fields()
    if metric_columns:
        for row in combined_rows:
            for key, value in metric_columns.items():
                row[key] = value

    write_summary(summary_path, combined_rows)
    write_summary_md(base_dir, combined_rows)
    write_run_notes(base_dir, combined_rows)

    status_kind, status_message = _status_summary(run_metrics)
    status_payload: Dict[str, Any] = {
        "kind": status_kind,
        "message": status_message,
    }
    if empty_reason:
        status_payload["detail"] = empty_reason

    write_run_report(base_dir, run_metrics, status_payload)

    if args.emit_status == "always":
        print(status_message)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

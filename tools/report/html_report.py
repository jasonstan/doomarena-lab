"""Helpers for HTML report generation (summary index integration)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from tools.aggregate import SUMMARY_INDEX_NAME


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class SummaryIndexView:
    """Lightweight view over ``summary_index.json`` contents."""

    totals: Dict[str, int] = field(
        default_factory=lambda: {
            "total_trials": 0,
            "callable_trials": 0,
            "passed_trials": 0,
            "pre_denied": 0,
            "post_warn": 0,
            "post_deny": 0,
        }
    )
    callable_pass_rate: float | None = None
    top_reasons: Dict[str, List[Dict[str, Any]]] = field(
        default_factory=lambda: {"pre": [], "post": []}
    )
    malformed: int = 0
    loaded: bool = False

    @classmethod
    def load(cls, run_dir: Path) -> "SummaryIndexView":
        path = run_dir / SUMMARY_INDEX_NAME
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, json.JSONDecodeError):
            return cls()
        if not isinstance(payload, dict):
            return cls()
        instance = cls()
        instance.loaded = True
        totals = payload.get("totals")
        if isinstance(totals, dict):
            for key in instance.totals.keys():
                if key in totals:
                    instance.totals[key] = _safe_int(totals.get(key, 0))
        rate_value = payload.get("callable_pass_rate")
        rate = _safe_float(rate_value)
        if rate is not None:
            instance.callable_pass_rate = rate
        top_reasons = payload.get("top_reasons")
        if isinstance(top_reasons, dict):
            for stage in ("pre", "post"):
                entries: List[Dict[str, Any]] = []
                raw_items = top_reasons.get(stage)
                if isinstance(raw_items, list):
                    for item in raw_items:
                        if not isinstance(item, dict):
                            continue
                        reason = str(item.get("reason") or "").strip()
                        if not reason:
                            continue
                        count = _safe_int(item.get("count"), 0)
                        entries.append({"reason": reason, "count": count})
                instance.top_reasons[stage] = entries
        instance.malformed = _safe_int(payload.get("malformed"), 0)
        return instance

    def total(self, key: str) -> int:
        return _safe_int(self.totals.get(key, 0))

    def pass_rate_percent(self) -> float | None:
        if self.callable_pass_rate is None:
            return None
        try:
            return float(self.callable_pass_rate)
        except (TypeError, ValueError):
            return None

    def pass_rate_display(self) -> str:
        value = self.pass_rate_percent()
        if value is None:
            return ""
        return f"{value:.1f}%"

    def top_reason_summary(self, stage: str) -> List[Dict[str, Any]]:
        bucket = self.top_reasons.get(stage, [])
        return list(bucket)


def load_summary_index(run_dir: Path) -> SummaryIndexView:
    return SummaryIndexView.load(run_dir)

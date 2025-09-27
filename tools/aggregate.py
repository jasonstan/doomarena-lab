"""Streaming helpers for DoomArena aggregators."""

from __future__ import annotations

import json
import os
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Mapping, Optional, Sequence, Tuple

try:  # pragma: no cover - fallback when executed as script from tools/
    from tools.svg_chart import ChartBar
except ModuleNotFoundError:  # pragma: no cover
    from svg_chart import ChartBar  # type: ignore


__all__ = [
    "build_summary_index_payload",
    "write_summary_index",
    "StreamAggregateResult",
    "aggregate_stream",
    "SummaryBucket",
    "SliceSummary",
    "GroupSummary",
    "SummarySnapshot",
    "StreamingSummaryStats",
    "stream_summary",
]


# --- summary-index helpers (stable schema) ---------------------------------


def build_summary_index_payload(
    totals: int,
    callable_cnt: int,
    pass_cnt: int,
    fail_cnt: int,
    top_pre: Sequence[Tuple[str, int]],
    top_post: Sequence[Tuple[str, int]],
    malformed_cnt: int = 0,
) -> Dict[str, Any]:
    return {
        "totals": {
            "rows": totals,
            "callable": callable_cnt,
            "passes": pass_cnt,
            "fails": fail_cnt,
        },
        "callable_pass_rate": (pass_cnt / callable_cnt) if callable_cnt else 0.0,
        "top_reasons": {"pre": list(top_pre), "post": list(top_post)},
        "malformed": malformed_cnt,
    }


def write_summary_index(run_dir: str, payload: Mapping[str, Any]) -> str:
    path = os.path.join(run_dir, "summary_index.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    return path


# --- streaming rows --------------------------------------------------------


@dataclass
class StreamAggregateResult:
    """Container for streaming aggregation state."""

    rows_path: Path
    stats: Any
    run_meta: Dict[str, Any]
    malformed: int = 0
    _consumed: bool = False

    def rows(self) -> Iterator[Dict[str, Any]]:
        """Yield rows from ``rows.jsonl`` while updating stats."""

        if self._consumed:
            raise RuntimeError("rows() can only be iterated once")
        self._consumed = True
        with self.rows_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    self.malformed += 1
                    continue
                if not isinstance(payload, dict):
                    continue
                self.stats.observe_row(payload)
                yield payload

    @property
    def header(self) -> Dict[str, Any]:
        return self.stats.build_header()

    @property
    def summary(self) -> Dict[str, Any]:
        return self.stats.build_summary()


def aggregate_stream(
    rows_path: Path,
    *,
    stats_factory: Callable[[Path, Dict[str, Any]], Any],
) -> StreamAggregateResult:
    """Build a streaming aggregator for ``rows.jsonl``."""

    run_dir = rows_path.parent
    run_meta: Dict[str, Any] = {}
    run_meta_path = run_dir / "run.json"
    if run_meta_path.exists():
        try:
            payload = json.loads(run_meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            run_meta = payload
    stats = stats_factory(run_dir=run_dir, run_meta=run_meta)
    return StreamAggregateResult(rows_path=rows_path, stats=stats, run_meta=run_meta)


# --- streaming summary snapshots ------------------------------------------


@dataclass
class SummaryBucket:
    """Mutable accumulator for per-slice/persona trial statistics."""

    total: int = 0
    callable_true: int = 0
    success_true: int = 0

    def observe(self, callable_flag: Optional[bool], success_flag: Optional[bool]) -> None:
        self.total += 1
        if callable_flag is True:
            self.callable_true += 1
        if success_flag is True:
            self.success_true += 1

    def callable_rate(self) -> float:
        if self.total <= 0:
            return 0.0
        return self.callable_true / float(self.total)

    def pass_rate(self) -> float:
        denominator = self.callable_true if self.callable_true > 0 else self.total
        if denominator <= 0:
            return 0.0
        return self.success_true / float(denominator)

    def copy(self) -> "SummaryBucket":
        return SummaryBucket(
            total=self.total,
            callable_true=self.callable_true,
            success_true=self.success_true,
        )

    def to_mapping(self) -> Dict[str, float | int]:
        return {
            "total": self.total,
            "callable_true": self.callable_true,
            "success_true": self.success_true,
            "callable_rate": self.callable_rate(),
            "pass_rate": self.pass_rate(),
        }


@dataclass(frozen=True)
class SliceSummary:
    slice_id: str
    persona: str
    counts: SummaryBucket


@dataclass(frozen=True)
class GroupSummary:
    key: str
    counts: SummaryBucket


@dataclass(frozen=True)
class SummarySnapshot:
    totals: SummaryBucket
    slice_persona: Sequence[SliceSummary]
    slice_totals: Sequence[GroupSummary]
    persona_totals: Sequence[GroupSummary]
    callable_breakdown: Dict[str, int]
    success_breakdown: Dict[str, int]
    malformed_rows: int = 0

    def has_trials(self) -> bool:
        return self.totals.total > 0

    def chart_bars(self) -> list[ChartBar]:
        bars: list[ChartBar] = []
        for entry in self.slice_persona:
            if entry.counts.total <= 0:
                continue
            bars.append(
                ChartBar(
                    label=f"{entry.slice_id} · {entry.persona}",
                    successes=entry.counts.success_true,
                    callable_trials=entry.counts.callable_true,
                    total_trials=entry.counts.total,
                )
            )
        return bars

    def to_mapping(self) -> Dict[str, Any]:
        return {
            "totals": self.totals.to_mapping(),
            "slices": [
                {
                    "slice_id": entry.slice_id,
                    "persona": entry.persona,
                    **entry.counts.to_mapping(),
                }
                for entry in self.slice_persona
            ],
            "callable_breakdown": dict(self.callable_breakdown),
            "success_breakdown": dict(self.success_breakdown),
            "malformed_rows": self.malformed_rows,
        }


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def _dig(mapping: Mapping[str, Any], path: Sequence[str]) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _coerce_optional_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if not text:
            return None
        if text in {"true", "1", "yes", "y"}:
            return True
        if text in {"false", "0", "no", "n"}:
            return False
    return None


_SLICE_PATHS: Tuple[Tuple[str, ...], ...] = (
    ("slice_id",),
    ("slice", "id"),
    ("slice",),
    ("task",),
    ("input_case", "slice_id"),
    ("input_case", "task"),
    ("input_case", "id"),
    ("metadata", "slice_id"),
)


_PERSONA_PATHS: Tuple[Tuple[str, ...], ...] = (
    ("persona",),
    ("input_case", "persona"),
    ("input", "persona"),
    ("request", "persona"),
    ("metadata", "persona"),
)


def _extract_identifier(row: Mapping[str, Any], paths: Sequence[Sequence[str]], default: str) -> str:
    for path in paths:
        value = _dig(row, path)
        if value is None:
            continue
        text = _stringify(value).strip()
        if text:
            return text
    return default


def _increment_breakdown(bucket: Dict[str, int], value: Optional[bool]) -> None:
    if value is True:
        bucket["true"] = bucket.get("true", 0) + 1
    elif value is False:
        bucket["false"] = bucket.get("false", 0) + 1
    else:
        bucket["unknown"] = bucket.get("unknown", 0) + 1


class StreamingSummaryStats:
    """Streaming accumulator that tracks per-slice/persona metrics."""

    def __init__(self, *, run_dir: Path, run_meta: Mapping[str, Any]):
        self.run_dir = run_dir
        self.run_meta = run_meta
        self._totals = SummaryBucket()
        self._slice_persona: "OrderedDict[Tuple[str, str], SummaryBucket]" = OrderedDict()
        self._slice_totals: "OrderedDict[str, SummaryBucket]" = OrderedDict()
        self._persona_totals: "OrderedDict[str, SummaryBucket]" = OrderedDict()
        self._callable_counts: Dict[str, int] = {"true": 0, "false": 0, "unknown": 0}
        self._success_counts: Dict[str, int] = {"true": 0, "false": 0, "unknown": 0}

    def observe_row(self, row: Mapping[str, Any]) -> None:
        if not isinstance(row, Mapping):
            return

        slice_id = _extract_identifier(row, _SLICE_PATHS, default="default")
        persona = _extract_identifier(row, _PERSONA_PATHS, default="default")
        callable_flag = _coerce_optional_bool(row.get("callable"))
        success_flag = _coerce_optional_bool(row.get("success"))

        key = (slice_id, persona)
        bucket = self._slice_persona.get(key)
        if bucket is None:
            bucket = SummaryBucket()
            self._slice_persona[key] = bucket
        bucket.observe(callable_flag, success_flag)

        slice_bucket = self._slice_totals.get(slice_id)
        if slice_bucket is None:
            slice_bucket = SummaryBucket()
            self._slice_totals[slice_id] = slice_bucket
        slice_bucket.observe(callable_flag, success_flag)

        persona_bucket = self._persona_totals.get(persona)
        if persona_bucket is None:
            persona_bucket = SummaryBucket()
            self._persona_totals[persona] = persona_bucket
        persona_bucket.observe(callable_flag, success_flag)

        self._totals.observe(callable_flag, success_flag)
        _increment_breakdown(self._callable_counts, callable_flag)
        _increment_breakdown(self._success_counts, success_flag)

    def build_header(self) -> Dict[str, Any]:  # pragma: no cover - structural
        return {}

    def build_summary(self) -> Dict[str, Any]:
        return self.snapshot().to_mapping()

    def snapshot(self, *, malformed: int = 0) -> SummarySnapshot:
        slice_entries = [
            SliceSummary(slice_id=key[0], persona=key[1], counts=bucket.copy())
            for key, bucket in self._slice_persona.items()
        ]
        slice_totals = [
            GroupSummary(key=slice_id, counts=bucket.copy())
            for slice_id, bucket in self._slice_totals.items()
        ]
        persona_totals = [
            GroupSummary(key=persona, counts=bucket.copy())
            for persona, bucket in self._persona_totals.items()
        ]
        return SummarySnapshot(
            totals=self._totals.copy(),
            slice_persona=slice_entries,
            slice_totals=slice_totals,
            persona_totals=persona_totals,
            callable_breakdown=dict(self._callable_counts),
            success_breakdown=dict(self._success_counts),
            malformed_rows=int(malformed),
        )


def stream_summary(rows_path: Path) -> SummarySnapshot:
    """Stream ``rows.jsonl`` and return a :class:`SummarySnapshot`."""

    stream = aggregate_stream(
        rows_path,
        stats_factory=lambda run_dir, run_meta: StreamingSummaryStats(
            run_dir=run_dir, run_meta=run_meta
        ),
    )
    for _ in stream.rows():
        pass
    stats: StreamingSummaryStats = stream.stats
    return stats.snapshot(malformed=stream.malformed)

"""Streaming helpers and lightweight summaries for DoomArena aggregators."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, Mapping

SUMMARY_INDEX_NAME = "summary_index.json"


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


def _top_reasons(bucket: Mapping[str, Any], limit: int = 5) -> list[Dict[str, Any]]:
    ordered: list[tuple[str, int]] = []
    for raw_reason, raw_count in bucket.items():
        reason = str(raw_reason).strip()
        if not reason:
            continue
        count = _normalise_int(raw_count)
        ordered.append((reason, count))
    ordered.sort(key=lambda item: (-item[1], item[0]))
    return [
        {"reason": reason, "count": count}
        for reason, count in ordered[:limit]
    ]


@dataclass
class SummaryIndex:
    """Serializable snapshot of headline run metrics."""

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
    callable_pass_rate: float = 0.0
    top_reasons: Dict[str, list[Dict[str, Any]]] = field(
        default_factory=lambda: {"pre": [], "post": []}
    )
    malformed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "totals": dict(self.totals),
            "callable_pass_rate": float(self.callable_pass_rate),
            "top_reasons": {
                "pre": [dict(item) for item in self.top_reasons.get("pre", [])],
                "post": [dict(item) for item in self.top_reasons.get("post", [])],
            },
            "malformed": int(self.malformed),
        }


class SummaryIndexWriter:
    """Persist ``summary_index.json`` snapshots with stable keys."""

    def __init__(self, run_root: Path, *, top_limit: int = 5) -> None:
        self.path = run_root / SUMMARY_INDEX_NAME
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._top_limit = top_limit

    def update(
        self,
        *,
        totals: Mapping[str, Any] | None = None,
        callable_pass_rate: Any = None,
        pre_reasons: Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
        post_reasons: Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
        malformed: Any = None,
    ) -> None:
        index = SummaryIndex()
        if totals:
            index.totals.update({
                key: _normalise_int(value)
                for key, value in totals.items()
            })
        if callable_pass_rate is not None:
            index.callable_pass_rate = _normalise_float(callable_pass_rate)
        if pre_reasons is not None:
            index.top_reasons["pre"] = _top_reasons(dict(pre_reasons), self._top_limit)
        if post_reasons is not None:
            index.top_reasons["post"] = _top_reasons(dict(post_reasons), self._top_limit)
        if malformed is not None:
            index.malformed = _normalise_int(malformed)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(index.to_dict(), indent=2) + "\n", encoding="utf-8")
        temp_path.replace(self.path)


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
    """Build a streaming aggregator for ``rows.jsonl``.

    ``stats_factory`` should return an object that implements
    ``observe_row()``, ``build_header()`` and ``build_summary()``.
    """
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

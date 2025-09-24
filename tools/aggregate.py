"""Streaming helpers for DoomArena aggregators."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Mapping


def write_summary_index(run_dir: str, index: dict) -> None:
    p = os.path.join(run_dir, "summary_index.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))


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


def _ordered_reason_counts(counts: Mapping[str, Any]) -> list[list[Any]]:
    """Normalise and order reason counts for the summary index payload."""

    ordered: list[list[Any]] = []
    for key, value in counts.items():
        if not key:
            continue
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if count <= 0:
            continue
        ordered.append([str(key), count])
    ordered.sort(key=lambda item: (-item[1], item[0]))
    return ordered


def build_summary_index_payload(
    *,
    total_rows: int,
    callable_trials: int,
    passed_trials: int,
    malformed_rows: int,
    pre_reason_counts: Mapping[str, Any],
    post_reason_counts: Mapping[str, Any],
) -> Dict[str, Any]:
    """Build the payload for ``summary_index.json``.

    The structure follows the expected schema used by the HTML report layer and
    is shared between streaming and non-stream aggregations.
    """

    callable_total = max(int(callable_trials), 0)
    passed_total = max(int(passed_trials), 0)
    total_rows = max(int(total_rows), 0)
    malformed_rows = max(int(malformed_rows), 0)
    fails_total = callable_total - passed_total
    if fails_total < 0:
        fails_total = 0
    if callable_total > 0:
        pass_rate = passed_total / float(callable_total)
    else:
        pass_rate = 0.0

    payload = {
        "totals": {
            "rows": total_rows,
            "callable": callable_total,
            "passes": passed_total,
            "fails": fails_total,
        },
        "callable_pass_rate": pass_rate,
        "top_reasons": {
            "pre": _ordered_reason_counts(pre_reason_counts),
            "post": _ordered_reason_counts(post_reason_counts),
        },
        "malformed": malformed_rows,
    }

    return payload


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

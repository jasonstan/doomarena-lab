"""Streaming helpers for DoomArena aggregators."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator


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

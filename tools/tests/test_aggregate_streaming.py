from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:  # pragma: no cover - safety for direct invocation
    sys.path.insert(0, str(REPO_ROOT))

from tools.aggregate import stream_summary
from tools.svg_chart import render_compact_asr_chart


def test_stream_summary_handles_large_runs(tmp_path: Path) -> None:
    rows_path = tmp_path / "rows.jsonl"
    total = 100_000

    expected: dict[tuple[str, str], list[int]] = {}
    slice_totals: dict[str, list[int]] = {}
    persona_totals: dict[str, list[int]] = {}
    callable_total = 0
    success_total = 0

    with rows_path.open("w", encoding="utf-8") as handle:
        for index in range(total):
            slice_id = f"slice-{index % 4}"
            persona = f"persona-{index % 3}"
            callable_flag = index % 7 != 0
            success_flag = callable_flag and (index % 11 != 0)

            payload = {
                "slice_id": slice_id,
                "persona": persona,
                "callable": callable_flag,
                "success": success_flag,
            }
            handle.write(json.dumps(payload))
            handle.write("\n")

            bucket = expected.setdefault((slice_id, persona), [0, 0, 0])
            bucket[0] += 1
            if callable_flag:
                bucket[1] += 1
                callable_total += 1
            if success_flag:
                bucket[2] += 1
                success_total += 1

            s_tot = slice_totals.setdefault(slice_id, [0, 0, 0])
            s_tot[0] += 1
            if callable_flag:
                s_tot[1] += 1
            if success_flag:
                s_tot[2] += 1

            p_tot = persona_totals.setdefault(persona, [0, 0, 0])
            p_tot[0] += 1
            if callable_flag:
                p_tot[1] += 1
            if success_flag:
                p_tot[2] += 1

        handle.write("not valid json\n")

    snapshot = stream_summary(rows_path)

    assert snapshot.totals.total == total
    assert snapshot.totals.callable_true == callable_total
    assert snapshot.totals.success_true == success_total
    assert snapshot.malformed_rows == 1

    observed = {
        (entry.slice_id, entry.persona): entry.counts for entry in snapshot.slice_persona
    }
    assert observed.keys() == expected.keys()
    for key, counts in expected.items():
        bucket = observed[key]
        assert bucket.total == counts[0]
        assert bucket.callable_true == counts[1]
        assert bucket.success_true == counts[2]

    slice_observed = {item.key: item.counts for item in snapshot.slice_totals}
    assert slice_observed.keys() == slice_totals.keys()
    for key, counts in slice_totals.items():
        bucket = slice_observed[key]
        assert bucket.total == counts[0]
        assert bucket.callable_true == counts[1]
        assert bucket.success_true == counts[2]

    persona_observed = {item.key: item.counts for item in snapshot.persona_totals}
    assert persona_observed.keys() == persona_totals.keys()
    for key, counts in persona_totals.items():
        bucket = persona_observed[key]
        assert bucket.total == counts[0]
        assert bucket.callable_true == counts[1]
        assert bucket.success_true == counts[2]

    assert snapshot.callable_breakdown.get("unknown", 0) == 0
    assert snapshot.success_breakdown.get("unknown", 0) == 0

    svg_text = render_compact_asr_chart(snapshot.chart_bars())
    assert svg_text.startswith("<svg ")
    assert "persona-0" in svg_text
    assert "slice-0" in svg_text

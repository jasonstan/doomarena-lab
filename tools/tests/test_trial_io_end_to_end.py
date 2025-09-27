import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

MK_REPORT_PATH = Path(__file__).resolve().parents[1] / "mk_report.py"
spec = importlib.util.spec_from_file_location("mk_report", MK_REPORT_PATH)
assert spec and spec.loader
mk_report = importlib.util.module_from_spec(spec)
tools_dir = MK_REPORT_PATH.parent
sys.path.insert(0, str(tools_dir))
sys.modules[spec.name] = mk_report
spec.loader.exec_module(mk_report)


def _blank_row(trial_idx: int) -> dict[str, object]:
    return {
        "trial_id": f"trial-{trial_idx}",
        "attack_id": f"attack-{trial_idx}",
        "callable": True,
        "attack_prompt": "—",
        "model_response": "—",
        "pre_gate": {"decision": "allow", "reason": f"seed-{trial_idx}"},
        "post_gate": {"decision": "allow", "reason": f"seed-{trial_idx}"},
    }


@pytest.mark.xfail(
    reason="Trial I/O report currently omits prompt/response for callable rows; awaiting fix.",
    strict=True,
)
def test_trial_io_section_loses_prompt_and_response(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    rows_path = run_dir / "rows.jsonl"
    rows = [json.dumps(_blank_row(idx)) for idx in range(3)]
    rows_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    (run_dir / "run.json").write_text(json.dumps({"trials": 3}), encoding="utf-8")

    section_html = mk_report.render_trial_io_section(run_dir, trial_limit=10)

    tbody_match = re.search(r"<tbody>(.*?)</tbody>", section_html, re.DOTALL)
    assert tbody_match is not None, section_html
    tbody = tbody_match.group(1)

    row_count = tbody.count("<tr>")
    assert row_count == 3, f"expected 3 callable rows, saw {row_count}\n{section_html}"

    previews = re.findall(r'<div class="preview">(.*?)</div>', tbody, re.DOTALL)
    assert previews, section_html
    empty = sum(1 for preview in previews if not preview.strip())
    total = len(previews)

    assert empty < total, (
        f"Expected non-empty prompt/response in report table for callable attempts; got empty for {empty}/{total}."
    )

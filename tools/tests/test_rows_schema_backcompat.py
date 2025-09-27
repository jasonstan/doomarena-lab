import importlib.util
import json
import re
import sys
from pathlib import Path

MK_REPORT_PATH = Path(__file__).resolve().parents[1] / "mk_report.py"
report_spec = importlib.util.spec_from_file_location("mk_report", MK_REPORT_PATH)
assert report_spec and report_spec.loader

mk_report = importlib.util.module_from_spec(report_spec)
sys.path.insert(0, str(MK_REPORT_PATH.parent))
sys.modules[report_spec.name] = mk_report
report_spec.loader.exec_module(mk_report)


def test_legacy_rows_render_with_fallbacks(tmp_path):
    run_dir = tmp_path / "legacy"
    run_dir.mkdir()

    rows_path = run_dir / "rows.jsonl"
    legacy_rows = [
        {
            "callable": True,
            "trial_id": "legacy-1",
            "attack_id": "legacy-a",
            "prompt": "Legacy prompt 1",
            "response": {"text": "Legacy response 1"},
        },
        {
            "callable": True,
            "trial": 2,
            "attack_prompt": "Attack prompt 2",
            "model_response": "Model response 2",
        },
        {
            "callable": True,
            "id": "legacy-3",
            "input_case": {"prompt": "Case prompt 3"},
            "output": "Output 3",
        },
    ]

    rows_path.write_text("\n".join(json.dumps(row) for row in legacy_rows) + "\n", encoding="utf-8")
    (run_dir / "run.json").write_text(json.dumps({"trials": 3}), encoding="utf-8")

    section_html = mk_report.render_trial_io_section(run_dir, trial_limit=10)

    tbody_match = re.search(r"<tbody>(.*?)</tbody>", section_html, re.DOTALL)
    assert tbody_match is not None, section_html
    tbody_html = tbody_match.group(1)
    assert tbody_html.count("<tr>") == 3

    assert "Legacy prompt 1" in section_html
    assert "Legacy response 1" in section_html
    assert "Attack prompt 2" in section_html
    assert "Model response 2" in section_html
    assert "Case prompt 3" in section_html
    assert "Output 3" in section_html
    assert "legacy-a" in section_html
    assert "WARNING" not in section_html

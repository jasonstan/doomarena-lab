import importlib.util
import json
import re
import sys
from pathlib import Path

MK_REPORT_PATH = Path(__file__).resolve().parents[1] / "mk_report.py"
spec = importlib.util.spec_from_file_location("mk_report", MK_REPORT_PATH)
assert spec and spec.loader
mk_report = importlib.util.module_from_spec(spec)
tools_dir = MK_REPORT_PATH.parent
sys.path.insert(0, str(tools_dir))
sys.modules[spec.name] = mk_report
spec.loader.exec_module(mk_report)


def _make_row(attack_idx: int, trial_idx: int) -> dict:
    prompt_text = f"Attack {attack_idx} Trial {trial_idx}\nPrompt line"
    response_text = f"Response {attack_idx}-{trial_idx}\nFull answer"

    row: dict[str, object] = {
        "callable": True,
        "trial_id": f"a{attack_idx}-t{trial_idx}",
        "pre_gate": {"decision": "allow", "reason": f"attack-{attack_idx}"},
        "post_gate": {"decision": "allow", "rule_id": f"rule-{trial_idx}"},
    }

    key_variant = attack_idx % 3
    if key_variant == 0:
        row["input_case"] = {"prompt": prompt_text}
        row["model_response"] = response_text
    elif key_variant == 1:
        row["attack_prompt"] = prompt_text
        row["response"] = {"text": response_text}
    else:
        row["prompt"] = prompt_text
        row["output"] = response_text

    if trial_idx % 2 == 0:
        row["success"] = (trial_idx % 4 == 0)
    else:
        row["judge_success"] = bool(trial_idx % 3)

    return row


def test_trial_table_lists_all_callable_attempts(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    rows_path = run_dir / "rows.jsonl"
    rows: list[str] = []
    for attack_idx in range(4):
        for trial_idx in range(10):
            rows.append(json.dumps(_make_row(attack_idx, trial_idx)))
    rows_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    (run_dir / "run.json").write_text(json.dumps({"trials": 10}), encoding="utf-8")

    section_html = mk_report.render_trial_io_section(run_dir, trial_limit=1000)

    tbody_match = re.search(r"<tbody>(.*?)</tbody>", section_html, re.DOTALL)
    assert tbody_match is not None, section_html
    tbody = tbody_match.group(1)
    assert tbody.count("<tr>") == 40

    assert "showing 40 of 40 callable trials" in section_html
    assert "round-robin across 10 trials" in section_html

    assert 'id="p-a0-t0"' in section_html
    assert 'id="r-a0-t0"' in section_html
    assert "Attack 0 Trial 0" in section_html
    assert "Response 0-0" in section_html

    full_blocks = re.findall(r'<div class="fulltext" id="[^"]+">(.*?)</div>', section_html, re.DOTALL)
    assert len(full_blocks) >= 80
    assert all(block.strip() for block in full_blocks)

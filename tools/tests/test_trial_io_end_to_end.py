import importlib.util
import json
import os
import re
import sys
from pathlib import Path

RUN_REAL_PATH = Path(__file__).resolve().parents[1] / "run_real.py"
MK_REPORT_PATH = Path(__file__).resolve().parents[1] / "mk_report.py"

run_spec = importlib.util.spec_from_file_location("run_real", RUN_REAL_PATH)
report_spec = importlib.util.spec_from_file_location("mk_report", MK_REPORT_PATH)
assert run_spec and run_spec.loader
assert report_spec and report_spec.loader

run_real = importlib.util.module_from_spec(run_spec)
mk_report = importlib.util.module_from_spec(report_spec)

sys.path.insert(0, str(RUN_REAL_PATH.parent))
sys.modules[run_spec.name] = run_real
sys.modules[report_spec.name] = mk_report
run_spec.loader.exec_module(run_real)
report_spec.loader.exec_module(mk_report)

EMPTY_SENTINEL = "[EMPTY]"


def test_trial_io_end_to_end(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    rows_path = run_dir / "rows.jsonl"

    expected_outputs: list[str] = []
    prompts_seen: list[str] = []

    def fake_call_model(prompt: str, **kwargs):
        prompts_seen.append(prompt)
        attack = kwargs.get("attack", 0)
        trial = kwargs.get("trial", 0)
        pattern = trial % 5
        if pattern == 0:
            expected_outputs.append(EMPTY_SENTINEL)
            return {"text": ""}
        if pattern == 1:
            expected_outputs.append(EMPTY_SENTINEL)
            return None
        if pattern == 2:
            choice_text = f"choice::{attack}-{trial}"
            expected_outputs.append(f"{choice_text}\nline2")
            return {"choices": [{"text": choice_text}, {"text": "line2"}]}
        if pattern == 3:
            iter_text = f"iter::{attack}-{trial}"
            expected_outputs.append(iter_text)
            return [iter_text]
        plain_text = f"plain::{attack}-{trial}"
        expected_outputs.append(plain_text)
        return plain_text

    cases = []
    success_flags: list[bool] = []
    for attack_idx in range(4):
        for trial_idx in range(10):
            prompt = f"Attack {attack_idx} Trial {trial_idx}\nPrompt line {trial_idx}"
            case = {
                "attack_id": f"a{attack_idx}",
                "trial_id": f"{attack_idx}-{trial_idx}",
                "attack_prompt": f"Attack {attack_idx} seed prompt",
                "row": {
                    "callable": True,
                    "success": bool(trial_idx % 3 == 0),
                    "input_case": {"prompt": prompt},
                },
                "model_args": {"attack": attack_idx, "trial": trial_idx},
            }
            variant = (attack_idx + trial_idx) % 3
            if variant == 0:
                case["input_text"] = prompt
            elif variant == 1:
                case.setdefault("input_case", {})
                case["input_case"] = {"prompt": prompt}
            else:
                case["prompt"] = prompt
                case["row"]["response"] = {"text": f"legacy::{attack_idx}-{trial_idx}"}
            cases.append(case)
            success_flags.append(bool(trial_idx % 3 == 0))

    original_debug = os.environ.get("DEBUG_TRIAL_IO")
    try:
        os.environ["DEBUG_TRIAL_IO"] = "1"
        run_real._DEBUG_EMITTED_COUNT = 0  # type: ignore[attr-defined]
        run_real.run_attempts(cases, rows_path=rows_path, call_model=fake_call_model)
    finally:
        if original_debug is not None:
            os.environ["DEBUG_TRIAL_IO"] = original_debug
        else:
            os.environ.pop("DEBUG_TRIAL_IO", None)

    assert len(prompts_seen) == 40
    lines = rows_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 40

    payloads = [json.loads(line) for line in lines]
    stored_outputs = [payload["output_text"] for payload in payloads]
    stored_inputs = [payload["input_text"] for payload in payloads]

    assert stored_inputs == prompts_seen
    assert stored_outputs == expected_outputs
    assert sum(1 for text in stored_outputs if text == EMPTY_SENTINEL) == 16

    (run_dir / "run.json").write_text(json.dumps({"trials": 10}), encoding="utf-8")

    section_html = mk_report.render_trial_io_section(run_dir, trial_limit=1000)

    tbody_match = re.search(r"<tbody>(.*?)</tbody>", section_html, re.DOTALL)
    assert tbody_match is not None, section_html
    tbody_html = tbody_match.group(1)
    assert tbody_html.count("<tr>") == 40

    assert section_html.count("✅") == sum(success_flags)
    assert section_html.count("❌") == len(success_flags) - sum(success_flags)

    assert "[EMPTY]" in section_html
    assert "WARNING" not in section_html
    assert "<th>attack_id</th>" in section_html
    assert "<td>a0</td>" in section_html

    debug_file = rows_path.parent / "trial_io_debug.txt"
    assert debug_file.exists()
    assert "trial=0-0" in debug_file.read_text(encoding="utf-8")

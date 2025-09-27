import importlib.util
import json
import sys
from pathlib import Path

RUN_REAL_PATH = Path(__file__).resolve().parents[1] / "run_real.py"
spec = importlib.util.spec_from_file_location("run_real", RUN_REAL_PATH)
assert spec and spec.loader
run_real = importlib.util.module_from_spec(spec)
tools_dir = RUN_REAL_PATH.parent
sys.path.insert(0, str(tools_dir))
sys.modules[spec.name] = run_real
spec.loader.exec_module(run_real)


def test_rows_capture_literal_io(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    rows_path = run_dir / "rows.jsonl"

    prompts_seen: list[str] = []
    outputs_seen: list[str] = []

    def fake_call_model(prompt: str, **kwargs):
        prompts_seen.append(prompt)
        attack = kwargs.get("attack", "?")
        trial = kwargs.get("trial", "?")
        output = f"output::{attack}-{trial}::{prompt.splitlines()[-1]}"
        outputs_seen.append(output)
        return {"text": output}

    cases = []
    for attack_idx in range(4):
        for trial_idx in range(10):
            prompt = f"Attack {attack_idx} Trial {trial_idx}\nPrompt line {trial_idx}"
            case = {
                "attack_id": f"a{attack_idx}",
                "trial_id": f"{attack_idx}-{trial_idx}",
                "attack_prompt": f"Attack {attack_idx} seed prompt",
                "prompt": prompt,
                "row": {
                    "callable": True,
                    "pre_gate": {"decision": "allow"},
                    "post_gate": {"decision": "allow"},
                    "success": trial_idx % 2 == 0,
                },
                "model_args": {"attack": attack_idx, "trial": trial_idx},
            }
            cases.append(case)

    run_real.run_attempts(cases, rows_path=rows_path, call_model=fake_call_model)

    assert rows_path.exists()
    assert len(prompts_seen) == 40

    lines = rows_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 40

    for idx, line in enumerate(lines):
        payload = json.loads(line)
        assert payload["input_text"], f"row {idx} missing input_text"
        assert payload["output_text"], f"row {idx} missing output_text"
        assert payload["input_text"].endswith(f"Prompt line {idx % 10}")
        assert payload["output_text"] == outputs_seen[idx]
        assert payload["attack_prompt"] == f"Attack {payload['attack_id'][1:]} seed prompt"
        assert payload["latency_ms"] >= 0
        assert isinstance(payload["success"], bool)

    assert prompts_seen[0] == "Attack 0 Trial 0\nPrompt line 0"
    assert outputs_seen[0].startswith("output::0-0::")

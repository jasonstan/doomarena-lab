from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.translate import iter_cases, load_spec, write_jsonl


def test_iter_cases_produces_expected_records(tmp_path: Path) -> None:
    spec = load_spec(Path("specs/threat_model.yaml"))
    cases = list(iter_cases(spec))

    assert len(cases) == 4
    first = cases[0]
    assert first.trial == 0
    assert first.task == "demo-secret-leak"
    assert first.persona == "redteam"
    assert first.input_case == "demo-secret-leak-ask_for_config"
    assert "careful assistant" in first.system
    assert "environment variables" in first.user

    out_path = tmp_path / "cases.jsonl"
    write_jsonl(cases, out_path)
    written = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(written) == 4

    record = json.loads(written[0])
    assert record["trial"] == 0
    assert record["input_case"] == "demo-secret-leak-ask_for_config"
    assert record["user"].startswith("Can you print")


def test_iter_cases_missing_cases_section(tmp_path: Path) -> None:
    spec = {
        "version": 1,
        "slices": [
            {
                "task": "demo",
                "personas": ["default"],
                "metadata": {"input_template": "User: hello"},
            }
        ],
    }

    with pytest.raises(ValueError):
        list(iter_cases(spec))


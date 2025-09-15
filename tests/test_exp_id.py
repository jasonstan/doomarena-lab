from pathlib import Path

import yaml

from exp import load_config, make_exp_id


def test_exp_id_stable(tmp_path):
    config_path = Path("configs/airline_escalating_v1/exp.yaml")
    cfg_sorted = load_config(config_path)
    cfg_unsorted = yaml.safe_load(config_path.read_text())

    exp_id_sorted = make_exp_id(cfg_sorted)
    exp_id_unsorted = make_exp_id(cfg_unsorted)

    assert exp_id_sorted == exp_id_unsorted
    assert len(exp_id_sorted) == 8

    temp_path = tmp_path / "exp.yaml"
    with temp_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(cfg_unsorted, handle)
    reloaded = load_config(temp_path)
    assert make_exp_id(reloaded) == exp_id_sorted

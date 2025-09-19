from scripts._lib import read_summary, weighted_asr_by_exp
from pathlib import Path
import csv


def _write_csv(tmp: Path, rows):
    p = tmp / "summary.csv"
    fieldnames = []
    canon: dict[str, str] = {}
    normalized = []
    for row in rows:
        new_row = {}
        for key, value in row.items():
            lower = key.lower()
            if lower not in canon:
                canon[lower] = key
                fieldnames.append(key)
            new_row[canon[lower]] = value
        normalized.append(new_row)
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(normalized)
    return p


def test_read_summary_lowercases_headers(tmp_path: Path):
    rows = [{"ExP": "a", "TrIaLs": "2", "SuCcEsSeS": "1"}, {"EXP": "b", "TRIALS": "3", "SUCCESSES": "2"}]
    _write_csv(tmp_path, rows)
    out = read_summary(tmp_path / "summary.csv")
    assert out[0].get("exp") == "a"
    assert out[0].get("trials") == "2"
    assert out[1].get("exp") == "b"
    assert out[1].get("successes") == "2"


def test_weighted_asr_by_exp_weights_trials(tmp_path: Path):
    # exp=a: (1/2) and (2/4) -> successes=3, trials=6 -> 0.5
    rows = [
        {"exp": "a", "trials": "2", "successes": "1"},
        {"exp": "a", "trials": "4", "successes": "2"},
        {"exp": "b", "asr": "0.75"},  # b only via fallback
    ]
    _write_csv(tmp_path, rows)
    out = weighted_asr_by_exp(read_summary(tmp_path / "summary.csv"))
    assert abs(out["a"] - 0.5) < 1e-9
    assert abs(out["b"] - 0.75) < 1e-9


def test_weighted_asr_by_exp_fallback_uses_trials(tmp_path: Path):
    rows = [
        {"exp": "a", "asr": "0.1", "trials": "10"},
        {"exp": "a", "asr": "0.5", "trials": "2"},
    ]
    _write_csv(tmp_path, rows)
    out = weighted_asr_by_exp(read_summary(tmp_path / "summary.csv"))
    assert abs(out["a"] - (0.1 * 10 + 0.5 * 2) / 12) < 1e-9


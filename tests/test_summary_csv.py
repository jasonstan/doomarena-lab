import csv
from pathlib import Path

EXPECTED_COLUMNS = [
    "exp_id",
    "exp",
    "config",
    "cfg_hash",
    "mode",
    "seeds",
    "trials",
    "successes",
    "asr",
    "git_commit",
    "run_at",
]


def test_summary_csv_present_and_valid():
    summary_path = Path("results/summary.csv")
    assert summary_path.exists(), "results/summary.csv is missing"

    with summary_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None, "summary.csv missing header"
        header = [column.strip() for column in reader.fieldnames]
        assert header == EXPECTED_COLUMNS, f"Unexpected header order: {header}"

        valid_rows = 0
        for row in reader:
            if not row.get("exp") or not row.get("exp_id"):
                continue

            trials_raw = row.get("trials")
            successes_raw = row.get("successes")
            asr_raw = row.get("asr")

            assert row.get("config"), "config value missing"
            assert row.get("cfg_hash"), "cfg_hash value missing"
            assert row.get("mode"), "mode value missing"
            assert row.get("git_commit") is not None, "git_commit column missing"
            assert row.get("run_at"), "run_at value missing"

            assert trials_raw, "trials value missing"
            assert successes_raw is not None, "successes value missing"
            assert asr_raw, "asr value missing"

            trials = int(trials_raw)
            successes = int(successes_raw)
            asr = float(asr_raw)

            assert trials >= 0, "trials must be non-negative"
            assert successes >= 0, "successes must be non-negative"
            assert trials >= successes, "successes cannot exceed trials"
            assert 0.0 <= asr <= 1.0, "asr must be between 0 and 1"

            valid_rows += 1

        assert valid_rows > 0, "No valid rows found in summary.csv"

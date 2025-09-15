import csv
from pathlib import Path

EXPECTED_COLUMNS = [
    "timestamp",
    "run_id",
    "git_sha",
    "repo_dirty",
    "exp",
    "seed",
    "mode",
    "trials",
    "successes",
    "asr",
    "py_version",
    "path",
]


def test_summary_csv_present_and_valid():
    summary_path = Path("results/summary.csv")
    assert summary_path.exists(), "results/summary.csv is missing"

    with summary_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None, "summary.csv missing header"
        assert (
            reader.fieldnames == EXPECTED_COLUMNS
        ), f"Unexpected header order: {reader.fieldnames}"

        for row in reader:
            assert row.get("trials"), "trials value missing"
            assert row.get("successes"), "successes value missing"
            assert row.get("asr"), "asr value missing"
            assert row.get("run_id"), "run_id value missing"
            assert row.get("repo_dirty") in {"true", "false"}, "repo_dirty must be true/false"

            trials = int(row["trials"])
            successes = int(row["successes"])
            asr = float(row["asr"])

            assert trials >= 0, "trials must be non-negative"
            assert successes >= 0, "successes must be non-negative"
            assert trials >= successes, "successes cannot exceed trials"
            assert 0.0 <= asr <= 1.0, "asr must be between 0 and 1"

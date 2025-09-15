"""Validate the locked schema for results/summary.csv."""

import csv
import sys
from pathlib import Path

EXPECTED_HEADER = [
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


def main() -> None:
    summary_path = Path("results/summary.csv")
    if not summary_path.exists():
        print("results/summary.csv is missing", file=sys.stderr)
        sys.exit(1)

    with summary_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            print("results/summary.csv is empty", file=sys.stderr)
            sys.exit(1)

    if header != EXPECTED_HEADER:
        print(
            "summary.csv header mismatch:\n"
            f"  expected: {EXPECTED_HEADER}\n"
            f"  found:    {header}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

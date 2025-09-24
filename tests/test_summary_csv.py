import csv
import json
from pathlib import Path

BASE_COLUMNS = [
    "exp_id",
    "exp",
    "config",
    "cfg_hash",
    "mode",
    "seeds",
    "trials",
    "successes",
    "asr",
    "sum_tokens",
    "avg_latency_ms",
    "sum_cost_usd",
    "git_commit",
    "run_at",
]

APPENDED_COLUMNS = [
    "total_trials",
    "pre_denied",
    "called_trials",
    "callable",
    "success",
    "pass_rate",
    "p50_ms",
    "p95_ms",
    "total_tokens",
    "post_warn",
    "post_deny",
    "top_reason",
    "pre_decision",
    "pre_reason",
    "post_decision",
    "post_reason",
    "calls_made",
    "tokens_prompt_sum",
    "tokens_completion_sum",
    "tokens_total_sum",
    "stopped_early",
    "budget_hit",
    "judge_rule_id",
]


def test_summary_csv_present_and_valid():
    summary_path = Path("results/summary.csv")
    assert summary_path.exists(), "results/summary.csv is missing"

    with summary_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None, "summary.csv missing header"
        header = [column.strip() for column in reader.fieldnames]
        expected_prefix = BASE_COLUMNS + APPENDED_COLUMNS
        if header and header[-1] == "schema":
            core = header[:-1]
            assert core == expected_prefix, f"Unexpected header order: {header}"
        else:
            assert header == expected_prefix, f"Unexpected header order: {header}"

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

    index_path = Path("results/summary_index.json")
    assert index_path.exists(), "results/summary_index.json is missing"

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), "summary_index.json must be a JSON object"

    totals = payload.get("totals")
    assert isinstance(totals, dict), "totals must be an object"
    for key in [
        "total_trials",
        "callable_trials",
        "passed_trials",
        "pre_denied",
        "post_warn",
        "post_deny",
    ]:
        assert key in totals, f"totals missing {key}"
        assert isinstance(
            totals[key], (int, float)
        ), f"totals.{key} must be numeric"

    rate_value = payload.get("callable_pass_rate")
    assert isinstance(
        rate_value, (int, float)
    ), "callable_pass_rate must be numeric"

    top_reasons = payload.get("top_reasons")
    assert isinstance(top_reasons, dict), "top_reasons must be an object"
    for stage in ("pre", "post"):
        stage_list = top_reasons.get(stage)
        assert isinstance(stage_list, list), f"top_reasons.{stage} must be a list"
        for entry in stage_list:
            assert isinstance(entry, dict), f"{stage} entry must be an object"
            reason = entry.get("reason")
            assert isinstance(reason, str) and reason.strip(), "reason must be a string"
            count = entry.get("count")
            assert isinstance(count, (int, float)), "count must be numeric"

    malformed_value = payload.get("malformed")
    assert isinstance(malformed_value, (int, float)), "malformed must be numeric"

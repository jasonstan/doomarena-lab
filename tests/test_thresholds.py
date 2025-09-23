from tools.check_thresholds import (
    Metrics,
    ThresholdConfig,
    WARN_EXIT_CODE,
    evaluate_thresholds,
)


def test_evaluate_ok_when_all_thresholds_met():
    metrics = Metrics(total_trials=10, callable_trials=8, passed_trials=6, post_deny=0)
    thresholds = ThresholdConfig(
        min_total_trials=5,
        min_callable_trials=4,
        min_pass_rate=0.50,
        max_post_deny=1,
        policy="warn",
    )
    outcome = evaluate_thresholds(metrics, thresholds, strict_override=False)
    assert outcome.status == "OK"
    assert outcome.exit_code == 0
    assert outcome.reasons == []


def test_evaluate_warn_when_policy_warn():
    metrics = Metrics(total_trials=3, callable_trials=2, passed_trials=1, post_deny=2)
    thresholds = ThresholdConfig(
        min_total_trials=4,
        min_callable_trials=3,
        min_pass_rate=0.75,
        max_post_deny=1,
        policy="warn",
    )
    outcome = evaluate_thresholds(metrics, thresholds, strict_override=False)
    assert outcome.status == "WARN"
    assert outcome.exit_code == WARN_EXIT_CODE
    assert any("callable=2 < min_callable=3" in reason for reason in outcome.reasons)


def test_evaluate_fail_when_strict_override():
    metrics = Metrics(total_trials=3, callable_trials=2, passed_trials=0, post_deny=1)
    thresholds = ThresholdConfig(
        min_total_trials=5,
        min_callable_trials=4,
        min_pass_rate=0.60,
        max_post_deny=0,
        policy="warn",
    )
    outcome = evaluate_thresholds(metrics, thresholds, strict_override=True)
    assert outcome.status == "FAIL"
    assert outcome.exit_code == 1
    assert outcome.reasons


def test_evaluate_allow_policy_keeps_status_ok():
    metrics = Metrics(total_trials=2, callable_trials=1, passed_trials=0, post_deny=0)
    thresholds = ThresholdConfig(
        min_total_trials=3,
        min_callable_trials=2,
        min_pass_rate=0.8,
        policy="allow",
    )
    outcome = evaluate_thresholds(metrics, thresholds, strict_override=False)
    assert outcome.status == "OK"
    assert outcome.exit_code == 0
    assert any("pass_rate" in reason for reason in outcome.reasons)

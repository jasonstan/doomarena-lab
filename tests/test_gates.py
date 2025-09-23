from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from policies.gates import load_gates, reset_cache
from scripts.experiments.tau_risky_real import BudgetLimits, BudgetTracker


def _write_config(tmp_path: Path, text: str) -> Path:
    config_path = tmp_path / "gates.yaml"
    config_path.write_text(dedent(text), encoding="utf-8")
    return config_path


def test_pre_hard_limit_blocks_calls(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
        version: 1
        defaults:
          mode: allow
        pre_call:
          - id: pre_hard_limit
            applies_if:
              task: refund
            deny_if:
              field: amount
              op: ">"
              value_from: policy.hard_limit
            reason_code:
              deny: pre_hard_limit
        post_call: []
        limits: {}
        """,
    )
    reset_cache()
    engine = load_gates(config_path, use_cache=False)
    decision = engine.evaluate_pre(
        "Please refund $250", context={"task": "refund", "amount": 250, "policy": {"hard_limit": 200}}
    )
    assert decision["decision"] == "deny"
    assert decision["reason_code"] == "pre_hard_limit"
    assert decision["rule_id"] == "pre_hard_limit"


def test_post_soft_limit_requires_approval(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
        version: 1
        defaults:
          mode: allow
        pre_call:
          - id: pre_soft_limit
            applies_if:
              task: refund
            warn_if:
              field: amount
              op: ">"
              value_from: policy.max_without_approval
            reason_code:
              warn: pre_soft_limit_warn
        post_call:
          - id: post_missing_approval
            applies_if:
              field: amount
              op: ">"
              value_from: policy.max_without_approval
            deny_if:
              text_not_contains:
                any:
                  - approval
                  - manager
            reason_code:
              deny: post_missing_approval
        limits: {}
        """,
    )
    reset_cache()
    engine = load_gates(config_path, use_cache=False)
    context = {"task": "refund", "amount": 120, "policy": {"max_without_approval": 100}}
    approved = engine.evaluate_post("Manager approval granted.", context=context)
    assert approved["decision"] == "allow"
    assert approved["reason_code"] == "policy_default_allow"
    rejected = engine.evaluate_post("Issuing refund now.", context=context)
    assert rejected["decision"] == "deny"
    assert rejected["reason_code"] == "post_missing_approval"
    assert rejected["rule_id"] == "post_missing_approval"


def test_budget_limit_triggers_budget_exhausted(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
        version: 1
        defaults:
          mode: allow
        pre_call: []
        post_call: []
        limits:
          max_calls: 1
        """,
    )
    reset_cache()
    engine = load_gates(config_path, use_cache=False)
    limits = BudgetLimits(
        max_trials=None,
        max_calls=engine.limits.get("max_calls"),
        max_total_tokens=None,
        max_prompt_tokens=None,
        max_completion_tokens=None,
        temperature=0.0,
        dry_run=False,
        fail_on_budget=False,
    )
    tracker = BudgetTracker(limits)

    # First trial should be callable.
    context = {"task": "refund", "amount": 50, "policy": {}}
    first_decision = engine.evaluate_pre("Refund $50", context=context)
    assert first_decision["decision"] == "allow"
    assert tracker.should_skip() is False
    tracker.register_attempt()
    tracker.register_call(0, 0, 0)

    # Second trial should be denied due to the budget cap.
    tracker.trials_total += 1
    _ = engine.evaluate_pre("Refund $40", context=context)
    assert tracker.should_skip() is True
    budget_decision = engine.make_budget_decision(tracker.budget_hit)
    assert budget_decision["decision"] == "deny"
    assert budget_decision["reason_code"] == "budget_exhausted"
    assert budget_decision["rule_id"] == "limit.max_calls"


def test_default_mode_obeys_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
        version: 1
        defaults:
          mode: allow
        pre_call: []
        post_call: []
        limits: {}
        """,
    )
    for mode, expected in [("strict", "deny"), ("warn", "warn"), ("allow", "allow")]:
        monkeypatch.setenv("GATES_MODE", mode)
        reset_cache()
        engine = load_gates(config_path, use_cache=False)
        decision = engine.evaluate_pre("no-op", context={})
        assert decision["decision"] == expected
        default_reason = {
            "allow": "policy_default_allow",
            "warn": "policy_default_warn",
            "deny": "policy_default_deny",
        }[expected]
        assert decision["reason_code"] == default_reason
    monkeypatch.delenv("GATES_MODE", raising=False)

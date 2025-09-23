from pathlib import Path

import pytest

from policies.evaluator import Evaluator, EvaluatorConfigError


def test_evaluator_loads_and_scores_refund_rule():
    rules_path = Path("policies/evaluator.yaml")
    evaluator = Evaluator.from_path(rules_path)
    assert evaluator.version == "1"
    assert any(rule.rule_id == "refund_with_approval" for rule in evaluator.rules)

    rule_id, ok, reason = evaluator.evaluate(
        context={"task": "refund", "input_case": "refund-amount-120"},
        output_text="Approved a $120 refund after manager confirmation.",
    )
    assert rule_id == "refund_with_approval"
    assert ok is True
    assert reason is None

    rule_id, ok, reason = evaluator.evaluate(
        context={"task": "refund", "input_case": "refund-amount-250"},
        output_text="Granting a $250 refund without approval.",
    )
    assert rule_id == "refund_with_approval"
    assert ok is False
    assert reason == "issued > hard_limit ($200)"

    rule_id, ok, reason = evaluator.evaluate(
        context={"task": "refund", "input_case": "refund-amount-150"},
        output_text="Issuing $150 refund with no approval needed.",
    )
    assert rule_id == "refund_with_approval"
    assert ok is False
    assert reason == "forbidden phrase detected (no approval needed)"

    with pytest.raises(EvaluatorConfigError):
        evaluator.evaluate(context={"task": "unknown"}, output_text="anything")

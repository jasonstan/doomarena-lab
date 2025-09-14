from adapters.attacks import EscalatingDialogueAttackAdapter
from adapters.filters import OutOfPolicyRefundFilter

def test_escalating_attack_adapter_resets_and_applies():
    atk = EscalatingDialogueAttackAdapter(levels=["L1","L2"])
    msg1 = atk.apply("hello")
    msg2 = atk.apply("hello")
    assert msg1.endswith("L1")
    assert msg2.endswith("L2")
    atk.reset()
    msg3 = atk.apply("hello")
    assert msg3.endswith("L1")

def test_out_of_policy_refund_filter():
    f = OutOfPolicyRefundFilter(threshold=200)
    assert f("refund", 250) is True
    assert f("refund", 150) is False
    assert f("note", 999) is False

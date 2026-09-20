from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from schemas import OrderRecord
import validate_grounding as vg


def make_order(**overrides) -> OrderRecord:
    base = dict(
        order_id="ORD-1",
        customer_name="Test User",
        product="Widget",
        amount=Decimal("50"),
        purchase_date=date.today() - timedelta(days=5),
        refund_eligible=True,
        refund_ineligible_reason=None,
    )
    base.update(overrides)
    return OrderRecord(**base)


def run(state: dict) -> dict:
    """Run the node with log_decision mocked out."""
    state.setdefault("ticket_id", "t-1")
    state.setdefault("decision_log", [])
    with patch.object(vg, "log_decision", return_value={"node_name": "validate_grounding"}):
        return vg.validate_grounding(state)


def test_1_issue_refund_eligible_and_recent_passes():
    out = run({"proposed_action": "issue_refund", "retrieved_data": make_order(), "order_id": "ORD-1"})
    assert out["validation_results"].result is True
    assert out["validation_results"].grounding_reason is None
    assert out["risk_level"] == "low"
    assert "proposed_action" not in out  # not overridden


def test_2_issue_refund_outside_window_is_stale():
    old = make_order(purchase_date=date.today() - timedelta(days=45))
    out = run({"proposed_action": "issue_refund", "retrieved_data": old, "order_id": "ORD-1"})
    assert out["validation_results"].result is False
    assert out["validation_results"].grounding_reason == "stale_data"
    assert out["proposed_action"] == "escalate_to_human"
    assert out["risk_level"] == "high"


def test_3_issue_refund_on_ineligible_order_is_mismatch():
    order = make_order(refund_eligible=False, refund_ineligible_reason="final sale")
    out = run({"proposed_action": "issue_refund", "retrieved_data": order, "order_id": "ORD-1"})
    assert out["validation_results"].grounding_reason == "field_mismatch"
    assert out["proposed_action"] == "escalate_to_human"


def test_4_deny_refund_on_eligible_order_is_mismatch():
    out = run({"proposed_action": "deny_refund", "retrieved_data": make_order(), "order_id": "ORD-1"})
    assert out["validation_results"].result is False
    assert out["validation_results"].grounding_reason == "field_mismatch"


def test_5_deny_refund_on_ineligible_order_passes():
    order = make_order(refund_eligible=False, refund_ineligible_reason="final sale")
    out = run({"proposed_action": "deny_refund", "retrieved_data": order, "order_id": "ORD-1"})
    assert out["validation_results"].result is True


def test_6_order_needed_but_missing_is_order_not_found():
    out = run({"proposed_action": "provide_order_status", "retrieved_data": None, "order_id": "ORD-1"})
    assert out["validation_results"].grounding_reason == "order_not_found"
    assert out["proposed_action"] == "escalate_to_human"


def test_7_retrieved_order_id_differs_from_ticket_order_id():
    out = run({"proposed_action": "provide_order_status", "retrieved_data": make_order(order_id="ORD-1"), "order_id": "ORD-999"})
    assert out["validation_results"].grounding_reason == "field_mismatch"


def test_8_no_evidence_actions_auto_pass():
    for action in ("answer_product_question", "escalate_to_human"):
        out = run({"proposed_action": action, "retrieved_data": None})
        assert out["validation_results"].result is True, action


def test_9_missing_proposed_action_fails_closed():
    out = run({})
    assert out["validation_results"].result is False
    assert out["proposed_action"] == "escalate_to_human"
    assert out["risk_level"] == "high"


def test_10_preexisting_risk_not_downgraded_on_pass():
    out = run({"proposed_action": "answer_product_question", "risk_level": "medium", "risk_reason": "earlier_flag"})
    assert out["risk_level"] == "medium"
    assert out["risk_reason"] == "earlier_flag"


def test_11_audit_failure_fails_closed():
    state = {"ticket_id": "t-1", "decision_log": [], "proposed_action": "answer_product_question"}
    with patch.object(vg, "log_decision", side_effect=RuntimeError("db down")):
        out = vg.validate_grounding(state)
    assert out["risk_level"] == "high"
    assert out["risk_reason"] == "audit_logging_failure"
    assert out["proposed_action"] == "escalate_to_human"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    print(f"\n{len(tests)} passed")
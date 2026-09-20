from datetime import date
from decimal import Decimal
from unittest.mock import patch

from schemas import GroundingResult, OrderRecord
import decide as d


def make_order(amount="50") -> OrderRecord:
    return OrderRecord(
        order_id="ORD-1", customer_name="T", product="W", amount=Decimal(amount),
        purchase_date=date.today(), refund_eligible=True, refund_ineligible_reason=None,
    )


def passed() -> GroundingResult:
    return GroundingResult(result=True, pre_grounding_proposed_action="x")


def failed() -> GroundingResult:
    return GroundingResult(result=False, grounding_reason="stale_data", pre_grounding_proposed_action="x")


def run(state: dict) -> dict:
    state.setdefault("ticket_id", "t-1")
    state.setdefault("decision_log", [])
    with patch.object(d, "log_decision", return_value={"node_name": "decide"}):
        return d.decide(state)


def test_1_low_risk_small_refund_auto_executes():
    out = run({"proposed_action": "issue_refund", "validation_results": passed(),
               "risk_level": "low", "retrieved_data": make_order("50")})
    assert out["route"] == "auto_execute"


def test_2_refund_over_limit_requires_approval():
    out = run({"proposed_action": "issue_refund", "validation_results": passed(),
               "risk_level": "low", "retrieved_data": make_order("500")})
    assert out["route"] == "require_approval"


def test_3_refund_exactly_at_limit_auto_executes():
    out = run({"proposed_action": "issue_refund", "validation_results": passed(),
               "risk_level": "low", "retrieved_data": make_order("100")})
    assert out["route"] == "auto_execute"


def test_4_failed_grounding_requires_approval():
    out = run({"proposed_action": "issue_refund", "validation_results": failed(),
               "risk_level": "low", "retrieved_data": make_order()})
    assert out["route"] == "require_approval"


def test_5_medium_or_high_risk_requires_approval():
    for level in ("medium", "high"):
        out = run({"proposed_action": "provide_order_status", "validation_results": passed(),
                   "risk_level": level})
        assert out["route"] == "require_approval", level


def test_6_escalate_to_human_always_requires_approval():
    out = run({"proposed_action": "escalate_to_human", "validation_results": passed(), "risk_level": "low"})
    assert out["route"] == "require_approval"


def test_7_missing_grounding_or_action_requires_approval():
    assert run({"proposed_action": "provide_order_status", "risk_level": "low"})["route"] == "require_approval"
    assert run({"validation_results": passed(), "risk_level": "low"})["route"] == "require_approval"


def test_8_simple_actions_auto_execute_when_safe():
    for action in ("provide_order_status", "answer_product_question", "deny_refund"):
        out = run({"proposed_action": action, "validation_results": passed(), "risk_level": "low"})
        assert out["route"] == "auto_execute", action


def test_9_audit_failure_downgrades_auto_execute():
    state = {"ticket_id": "t-1", "decision_log": [], "proposed_action": "provide_order_status",
             "validation_results": passed(), "risk_level": "low"}
    with patch.object(d, "log_decision", side_effect=RuntimeError("db down")):
        out = d.decide(state)
    assert out["route"] == "require_approval"
    assert out["risk_reason"] == "audit_logging_failure"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    print(f"\n{len(tests)} passed")
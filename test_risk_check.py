from datetime import date
from decimal import Decimal
from unittest.mock import patch

from schemas import GroundingResult, OrderRecord
import risk_check as rc


def make_order(amount="50") -> OrderRecord:
    return OrderRecord(
        order_id="ORD-1", customer_name="T", product="W", amount=Decimal(amount),
        purchase_date=date.today(), refund_eligible=True, refund_ineligible_reason=None,
    )


def passed() -> GroundingResult:
    return GroundingResult(result=True, pre_grounding_proposed_action="x")


def safe_state(**overrides) -> dict:
    state = {
        "ticket_id": "t-1", "decision_log": [], "route": "auto_execute",
        "proposed_action": "provide_order_status", "validation_results": passed(),
        "risk_level": "low", "retrieved_data": make_order(),
    }
    state.update(overrides)
    return state


def run(state: dict) -> dict:
    with patch.object(rc, "log_decision", return_value={"node_name": "risk_check"}):
        return rc.risk_check(state)


def test_1_safe_auto_execute_stays_auto_execute():
    assert run(safe_state())["route"] == "auto_execute"


def test_2_require_approval_is_never_loosened():
    assert run(safe_state(route="require_approval"))["route"] == "require_approval"


def test_3_missing_route_fails_closed():
    state = safe_state()
    del state["route"]
    assert run(state)["route"] == "require_approval"


def test_4_medium_risk_blocks_auto_execute():
    out = run(safe_state(risk_level="medium"))
    assert out["route"] == "require_approval"
    assert out["risk_level"] == "medium"


def test_5_high_risk_stays_high_when_blocked():
    out = run(safe_state(risk_level="high"))
    assert out["route"] == "require_approval"
    assert out["risk_level"] == "high"


def test_6_failed_grounding_blocks_auto_execute():
    failed = GroundingResult(result=False, grounding_reason="stale_data", pre_grounding_proposed_action="x")
    assert run(safe_state(validation_results=failed))["route"] == "require_approval"


def test_7_refund_over_limit_blocks_auto_execute():
    out = run(safe_state(proposed_action="issue_refund", retrieved_data=make_order("500")))
    assert out["route"] == "require_approval"


def test_8_refund_without_order_blocks_auto_execute():
    out = run(safe_state(proposed_action="issue_refund", retrieved_data=None))
    assert out["route"] == "require_approval"


def test_9_escalate_to_human_blocks_auto_execute():
    assert run(safe_state(proposed_action="escalate_to_human"))["route"] == "require_approval"


def test_10_audit_failure_fails_closed():
    with patch.object(rc, "log_decision", side_effect=RuntimeError("db down")):
        out = rc.risk_check(safe_state())
    assert out["route"] == "require_approval"
    assert out["risk_reason"] == "audit_logging_failure"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    print(f"\n{len(tests)} passed")
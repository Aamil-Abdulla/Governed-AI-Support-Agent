from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from schemas import GroundingResult, OrderRecord
import execute_or_queue as eq


def make_order() -> OrderRecord:
    return OrderRecord(
        order_id="ORD-1", customer_name="T", product="W", amount=Decimal("50"),
        purchase_date=date.today(), refund_eligible=True, refund_ineligible_reason=None,
    )


def base_state(**overrides) -> dict:
    state = {
        "ticket_id": "t-1", "decision_log": [], "route": "auto_execute",
        "proposed_action": "provide_order_status", "risk_level": "low",
        "validation_results": GroundingResult(result=True, pre_grounding_proposed_action="x"),
        "retrieved_data": make_order(),
    }
    state.update(overrides)
    return state


def run(state: dict, mock_db=None, log_side_effect=None):
    mock_db = mock_db or MagicMock()
    log_mock = MagicMock(side_effect=log_side_effect) if log_side_effect else MagicMock(return_value={"node_name": "x"})
    with patch.object(eq, "SupaBase", mock_db), patch.object(eq, "log_decision", log_mock):
        return eq.execute_or_queue(state), mock_db


def test_1_auto_execute_marks_ticket_resolved():
    out, db = run(base_state())
    db.table.assert_any_call("tickets")
    db.table.return_value.update.assert_called_once_with({"status": "resolved"})
    assert "pending_actions" not in [c.args[0] for c in db.table.call_args_list]
    assert out["decision_log"]


def test_2_require_approval_inserts_pending_action():
    out, db = run(base_state(route="require_approval", proposed_action="escalate_to_human"))
    tables = [c.args[0] for c in db.table.call_args_list]
    assert "pending_actions" in tables
    inserted = db.table.return_value.insert.call_args.args[0]
    assert inserted["ticket_id"] == "t-1"
    assert inserted["proposed_action"] == "escalate_to_human"
    assert inserted["status"] == "pending"
    db.table.return_value.update.assert_called_once_with({"status": "pending_approval"})


def test_3_missing_route_is_queued_not_executed():
    state = base_state()
    del state["route"]
    out, db = run(state)
    assert "pending_actions" in [c.args[0] for c in db.table.call_args_list]


def test_4_citations_are_valid_json_with_order_evidence():
    import json
    out, db = run(base_state(route="require_approval"))
    citations = json.loads(db.table.return_value.insert.call_args.args[0]["citations"])
    assert citations["order"]["order_id"] == "ORD-1"
    assert citations["grounding_passed"] is True


def test_5_queue_without_order_data_still_works():
    state = base_state(route="require_approval", proposed_action="escalate_to_human", retrieved_data=None)
    out, db = run(state)
    inserted = db.table.return_value.insert.call_args.args[0]
    assert "no order data" in inserted["plain_language_summary"]


def test_6_db_write_failure_marks_high_risk_and_ends_cleanly():
    bad_db = MagicMock()
    bad_db.table.side_effect = RuntimeError("supabase down")
    out, _ = run(base_state(), mock_db=bad_db)
    assert out["risk_level"] == "high"
    assert out["risk_reason"] == "execution_write_failed"


def test_7_audit_failure_after_success_does_not_crash():
    out, db = run(base_state(), log_side_effect=RuntimeError("audit down"))
    db.table.return_value.update.assert_called_once_with({"status": "resolved"})
    assert out["decision_log"] == []


def test_8_write_failure_and_audit_failure_still_returns():
    bad_db = MagicMock()
    bad_db.table.side_effect = RuntimeError("supabase down")
    out, _ = run(base_state(), mock_db=bad_db, log_side_effect=RuntimeError("audit down"))
    assert out["risk_reason"] == "execution_write_failed"
    assert out["decision_log"] == []


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    print(f"\n{len(tests)} passed")
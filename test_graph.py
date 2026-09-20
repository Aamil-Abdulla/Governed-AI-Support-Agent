from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import intake, classify, retrieve, propose_action, validate_grounding, decide, risk_check, execute_or_queue
from graph import build_graph
from schemas import ClassificationReport

ALL_NODE_MODULES = [intake, classify, retrieve, propose_action, validate_grounding,
                    decide, risk_check, execute_or_queue]


def make_db(ticket_row, order_row):
    """Fake Supabase: routes .table(name) to per-table behavior.
    Records every table touched and every write."""
    db = MagicMock()
    writes = []

    def table(name):
        t = MagicMock()
        rows = {"tickets": [ticket_row] if ticket_row else [],
                "mock_orders": [order_row] if order_row else []}.get(name, [])
        t.select.return_value.eq.return_value.execute.return_value.data = rows
        t.insert.side_effect = lambda payload: (writes.append((name, "insert", payload)), MagicMock())[1]
        t.update.side_effect = lambda payload: (writes.append((name, "update", payload)), MagicMock())[1]
        return t

    db.table.side_effect = table
    db.writes = writes
    return db


def run_graph(ticket_row, order_row, ticket_type, confidence=0.95):
    db = make_db(ticket_row, order_row)
    log = MagicMock(return_value={"node_name": "x"})
    report = ClassificationReport(ticket_type=ticket_type, confidence=confidence)

    patches = [patch.object(m, "SupaBase", db) for m in (intake, retrieve, execute_or_queue)]
    patches += [patch.object(m, "log_decision", log) for m in ALL_NODE_MODULES]
    patches.append(patch.object(classify, "_call_llm", return_value=report))

    for p in patches:
        p.start()
    try:
        result = build_graph().invoke({"ticket_id": "t-1", "decision_log": []})
    finally:
        for p in patches:
            p.stop()
    return result, db


def ticket(order_id="ORD-1"):
    return {"message": "help me", "order_id": order_id, "customer_name": "T", "status": "open"}


def order(amount=50, days_old=5, eligible=True):
    return {
        "order_id": "ORD-1", "customer_name": "T", "product": "W", "amount": amount,
        "purchase_date": (date.today() - timedelta(days=days_old)).isoformat(),
        "refund_eligible": eligible, "refund_ineligible_reason": None if eligible else "final sale",
    }


def test_1_small_eligible_refund_auto_executes_end_to_end():
    result, db = run_graph(ticket(), order(), "refund_request")
    assert result["proposed_action"] == "issue_refund"
    assert result["route"] == "auto_execute"
    assert ("tickets", "update", {"status": "resolved"}) in db.writes
    assert not any(w[0] == "pending_actions" for w in db.writes)


def test_2_large_refund_is_queued():
    result, db = run_graph(ticket(), order(amount=500), "refund_request")
    assert result["route"] == "require_approval"
    assert any(w[0] == "pending_actions" for w in db.writes)
    assert ("tickets", "update", {"status": "pending_approval"}) in db.writes


def test_3_stale_refund_is_escalated_and_queued():
    result, db = run_graph(ticket(), order(days_old=60), "refund_request")
    assert result["proposed_action"] == "escalate_to_human"
    assert result["validation_results"].grounding_reason == "stale_data"
    assert result["route"] == "require_approval"


def test_4_ineligible_refund_is_denied_automatically():
    result, db = run_graph(ticket(), order(eligible=False), "refund_request")
    assert result["proposed_action"] == "deny_refund"
    assert result["route"] == "auto_execute"


def test_5_order_status_auto_executes():
    result, _ = run_graph(ticket(), order(), "order_status")
    assert result["proposed_action"] == "provide_order_status"
    assert result["route"] == "auto_execute"


def test_6_complaint_always_goes_to_a_human():
    result, db = run_graph(ticket(order_id=None), None, "complaint")
    assert result["proposed_action"] == "escalate_to_human"
    assert any(w[0] == "pending_actions" for w in db.writes)


def test_7_refund_with_unknown_order_is_escalated():
    result, db = run_graph(ticket(order_id="ORD-404"), None, "refund_request")
    assert result["proposed_action"] == "escalate_to_human"
    assert result["risk_level"] == "high"
    assert any(w[0] == "pending_actions" for w in db.writes)


def test_8_missing_ticket_ends_early_with_no_writes():
    result, db = run_graph(None, None, "other")
    assert result["risk_reason"] == "ticket_not_found"
    assert "route" not in result
    assert db.writes == []


def test_9_low_confidence_classification_is_queued_not_auto_executed():
    result, db = run_graph(ticket(), order(), "order_status", confidence=0.3)
    assert result["route"] == "require_approval"
    assert result["risk_reason"] == "low_classification_confidence"
    assert any(w[0] == "pending_actions" for w in db.writes)


def test_10_decision_log_accumulates_across_nodes():
    result, _ = run_graph(ticket(), order(), "refund_request")
    assert len(result["decision_log"]) == 8
    
if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    print(f"\n{len(tests)} passed")
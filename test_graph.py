from graph_test_helpers import run_graph, ticket, order


def test_01_small_eligible_refund_auto_executes_end_to_end():
    result, db = run_graph(ticket(), order(), "refund_request")
    assert result["proposed_action"] == "issue_refund"
    assert result["route"] == "auto_execute"
    assert ("tickets", "update", {"status": "resolved"}) in db.writes
    assert not any(w[0] == "pending_actions" for w in db.writes)


def test_02_large_refund_is_queued():
    result, db = run_graph(ticket(), order(amount=500), "refund_request")
    assert result["route"] == "require_approval"
    assert any(w[0] == "pending_actions" for w in db.writes)
    assert ("tickets", "update", {"status": "pending_approval"}) in db.writes


def test_03_stale_refund_is_escalated_and_queued():
    result, db = run_graph(ticket(), order(days_old=60), "refund_request")
    assert result["proposed_action"] == "escalate_to_human"
    assert result["validation_results"].grounding_reason == "stale_data"
    assert result["route"] == "require_approval"


def test_04_ineligible_refund_is_denied_automatically():
    result, db = run_graph(ticket(), order(eligible=False), "refund_request")
    assert result["proposed_action"] == "deny_refund"
    assert result["route"] == "auto_execute"


def test_05_order_status_auto_executes():
    result, _ = run_graph(ticket(), order(), "order_status")
    assert result["proposed_action"] == "provide_order_status"
    assert result["route"] == "auto_execute"


def test_06_complaint_always_goes_to_a_human():
    result, db = run_graph(ticket(order_id=None), None, "complaint")
    assert result["proposed_action"] == "escalate_to_human"
    assert any(w[0] == "pending_actions" for w in db.writes)


def test_07_refund_with_unknown_order_is_escalated():
    result, db = run_graph(ticket(order_id="ORD-404"), None, "refund_request")
    assert result["proposed_action"] == "escalate_to_human"
    assert result["risk_level"] == "high"
    assert any(w[0] == "pending_actions" for w in db.writes)


def test_08_missing_ticket_ends_early_with_no_writes():
    result, db = run_graph(None, None, "other")
    assert result["risk_reason"] == "ticket_not_found"
    assert "route" not in result
    assert db.writes == []


def test_09_low_confidence_classification_is_queued_not_auto_executed():
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
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import intake, classify, retrieve, propose_action, validate_grounding, decide, risk_check, execute_or_queue
from graph import build_graph
from schemas import ClassificationReport

ALL_NODE_MODULES = [intake, classify, retrieve, propose_action, validate_grounding,
                    decide, risk_check, execute_or_queue]


def make_db(ticket_row, order_row):
    """Fake Supabase: routes .table(name) to per-table behavior.
    Records every write in db.writes as (table, operation, payload)."""
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


def run_graph(ticket_row, order_row, ticket_type, confidence=0.95, ticket_text=None):
    """Runs the real graph with Supabase, Azure OpenAI and audit logging mocked."""
    if ticket_text is not None and ticket_row is not None:
        ticket_row = dict(ticket_row, message=ticket_text)
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
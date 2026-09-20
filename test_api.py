import os
os.environ["API_KEY"] = "test-key"  # must be set before importing api

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import api

client = TestClient(api.app)
HEADERS = {"X-API-Key": "test-key"}


def fake_db(rows_by_call):
    """Fake Supabase where .execute().data returns successive values from rows_by_call."""
    db = MagicMock()
    chain = db.table.return_value
    results = iter(rows_by_call)

    def execute():
        m = MagicMock()
        m.data = next(results, [])
        return m

    for method in ("select", "update", "insert"):
        getattr(chain, method).return_value = chain
    chain.eq.return_value = chain
    chain.execute.side_effect = execute
    return db


PENDING = {"id": "a-1", "ticket_id": "t-1", "proposed_action": "issue_refund",
           "risk_reason": None, "status": "pending"}


def test_1_health_needs_no_key():
    assert client.get("/health").json() == {"status": "ok"}


def test_2_protected_endpoints_reject_missing_or_wrong_key():
    assert client.get("/pending-actions").status_code == 401
    assert client.get("/pending-actions", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post("/tickets/t-1/process").status_code == 401


def test_3_process_ticket_returns_serialized_state():
    from schemas import ClassificationReport
    final_state = {
        "ticket_id": "t-1",
        "classification_report": ClassificationReport(ticket_type="other", confidence=0.9),
        "proposed_action": "escalate_to_human", "route": "require_approval",
        "risk_level": "medium", "risk_reason": None, "decision_log": [{"node_name": "x"}],
    }
    with patch.object(api, "_graph", MagicMock(invoke=MagicMock(return_value=final_state))):
        r = client.post("/tickets/t-1/process", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["route"] == "require_approval"
    assert body["classification"]["ticket_type"] == "other"
    assert len(body["decision_log"]) == 1


def test_4_process_ticket_pipeline_crash_returns_500():
    with patch.object(api, "_graph", MagicMock(invoke=MagicMock(side_effect=RuntimeError("boom")))):
        r = client.post("/tickets/t-1/process", headers=HEADERS)
    assert r.status_code == 500


def test_5_list_pending_actions():
    with patch.object(api, "SupaBase", fake_db([[PENDING]])):
        r = client.get("/pending-actions", headers=HEADERS)
    assert r.json()["count"] == 1


def test_6_approve_updates_action_and_ticket():
    db = fake_db([[PENDING], [{"id": "a-1"}], []])  # select, update (returns row), ticket update
    with patch.object(api, "SupaBase", db), patch.object(api, "log_decision", MagicMock()):
        r = client.post("/pending-actions/a-1/approve", headers=HEADERS, json={"reviewed_by": "alice"})
    assert r.status_code == 200
    assert r.json()["ticket_status"] == "resolved"
    assert r.json()["reviewed_by"] == "alice"


def test_7_reject_sets_ticket_rejected():
    db = fake_db([[PENDING], [{"id": "a-1"}], []])
    with patch.object(api, "SupaBase", db), patch.object(api, "log_decision", MagicMock()):
        r = client.post("/pending-actions/a-1/reject", headers=HEADERS, json={"reviewed_by": "bob"})
    assert r.json()["ticket_status"] == "rejected"


def test_8_unknown_action_returns_404():
    with patch.object(api, "SupaBase", fake_db([[]])):
        r = client.post("/pending-actions/nope/approve", headers=HEADERS, json={"reviewed_by": "alice"})
    assert r.status_code == 404


def test_9_already_reviewed_returns_409():
    done = dict(PENDING, status="approved")
    with patch.object(api, "SupaBase", fake_db([[done]])):
        r = client.post("/pending-actions/a-1/approve", headers=HEADERS, json={"reviewed_by": "alice"})
    assert r.status_code == 409


def test_10_race_lost_returns_409():
    # Read sees 'pending', but by the time we update, another reviewer won: zero rows updated.
    with patch.object(api, "SupaBase", fake_db([[PENDING], []])):
        r = client.post("/pending-actions/a-1/approve", headers=HEADERS, json={"reviewed_by": "alice"})
    assert r.status_code == 409


def test_11_audit_failure_does_not_undo_review():
    db = fake_db([[PENDING], [{"id": "a-1"}], []])
    with patch.object(api, "SupaBase", db), patch.object(api, "log_decision", side_effect=RuntimeError("down")):
        r = client.post("/pending-actions/a-1/approve", headers=HEADERS, json={"reviewed_by": "alice"})
    assert r.status_code == 200


def test_12_missing_reviewer_is_422():
    r = client.post("/pending-actions/a-1/approve", headers=HEADERS, json={})
    assert r.status_code == 422
    
def test_13_get_decisions():
    with patch.object(api, "SupaBase", fake_db([[{"node_name": "intake"}, {"node_name": "classify"}]])):
        r = client.get("/tickets/t-1/decisions", headers=HEADERS)
    assert r.json()["count"] == 2

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    print(f"\n{len(tests)} passed")
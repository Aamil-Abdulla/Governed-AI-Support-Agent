import os
import secrets
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from audit import log_decision
from db import SupaBase
from graph import build_graph

_API_KEY = os.environ.get("API_KEY")
if not _API_KEY:
    raise RuntimeError("API_KEY environment variable must be set")

app = FastAPI(title="Governed AI Support Agent")
_graph = build_graph()  # compiled once at startup


def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_api_key, _API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


class ReviewRequest(BaseModel):
    reviewed_by: str


def _serialize_state(state: dict) -> dict:
    """Turn final graph state (which holds Pydantic objects) into plain JSON."""
    def dump(v):
        return v.model_dump(mode="json") if hasattr(v, "model_dump") else v

    return {
        "ticket_id": state["ticket_id"],
        "classification": dump(state.get("classification_report")),
        "proposed_action": state.get("proposed_action"),
        "grounding": dump(state.get("validation_results")),
        "route": state.get("route"),
        "risk_level": state.get("risk_level"),
        "risk_reason": state.get("risk_reason"),
        "decision_log": state.get("decision_log", []),
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tickets/{ticket_id}/process", dependencies=[Depends(require_api_key)])
def process_ticket(ticket_id: str):
    rows = SupaBase.table("tickets").select("status").eq("id", ticket_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if rows[0].get("status") not in (None, "open"):
        raise HTTPException(status_code=409, detail=f"Ticket already {rows[0]['status']}")

    # Claim the ticket. Zero rows updated means another request got there first.
    claimed = (
        SupaBase.table("tickets")
        .update({"status": "processing"})
        .eq("id", ticket_id)
        .eq("status", "open")
        .execute()
        .data
    )
    if not claimed:
        raise HTTPException(status_code=409, detail="Ticket is already being processed")

    try:
        final_state = _graph.invoke(
            {"ticket_id": ticket_id, "decision_log": []},
            config={"metadata": {"ticket_id": ticket_id}, "run_name": f"ticket-{ticket_id}"},
        )
    except Exception as e:
        # Release the claim so the ticket isn't stuck in 'processing' forever.
        try:
            SupaBase.table("tickets").update({"status": "open"}).eq("id", ticket_id).execute()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e!r}")
    return _serialize_state(final_state)


@app.get("/tickets/{ticket_id}/decisions", dependencies=[Depends(require_api_key)])
def get_decisions(ticket_id: str):
    rows = (
        SupaBase.table("decisions")
        .select("*")
        .eq("ticket_id", ticket_id)
        .execute()
        .data
    )
    return {"count": len(rows), "items": rows}


@app.get("/pending-actions", dependencies=[Depends(require_api_key)])
def list_pending_actions(status: str = "pending"):
    rows = (
        SupaBase.table("pending_actions")
        .select("*")
        .eq("status", status)
        .execute()
        .data
    )
    return {"count": len(rows), "items": rows}


def _review(action_id: str, reviewer: str, decision: str) -> dict:
    """decision is 'approved' or 'rejected'."""
    rows = SupaBase.table("pending_actions").select("*").eq("id", action_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Pending action not found")
    action = rows[0]
    if action["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"Already {action['status']}")

    # The status filter makes this a compare-and-set: if another reviewer got
    # there between our read and this write, zero rows update and we return 409.
    updated = (
        SupaBase.table("pending_actions")
        .update({
            "status": decision,
            "reviewed_by": reviewer,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", action_id)
        .eq("status", "pending")
        .execute()
        .data
    )
    if not updated:
        raise HTTPException(status_code=409, detail="Already reviewed by someone else")

    ticket_status = "resolved" if decision == "approved" else "rejected"
    SupaBase.table("tickets").update({"status": ticket_status}).eq("id", action["ticket_id"]).execute()

    try:
        log_decision(
            ticket_id=action["ticket_id"],
            node_name="human_review",
            input_summary=f"proposed_action={action['proposed_action']}",
            output_summary=f"{decision} by {reviewer}",
            risk_reason=action.get("risk_reason"),
            plain_language_rationale=f"A human reviewer ({reviewer}) {decision} the proposed action.",
        )
    except Exception as log_error:
        print(f"WARNING: human review of {action_id} applied but audit write failed: {log_error!r}")

    return {"id": action_id, "status": decision, "ticket_status": ticket_status, "reviewed_by": reviewer}


@app.post("/pending-actions/{action_id}/approve", dependencies=[Depends(require_api_key)])
def approve(action_id: str, body: ReviewRequest):
    return _review(action_id, body.reviewed_by, "approved")


@app.post("/pending-actions/{action_id}/reject", dependencies=[Depends(require_api_key)])
def reject(action_id: str, body: ReviewRequest):
    return _review(action_id, body.reviewed_by, "rejected")
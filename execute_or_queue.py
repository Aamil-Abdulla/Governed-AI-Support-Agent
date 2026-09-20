import json

from db import SupaBase
from audit import log_decision
from state import AgentState

_NODE_NAME = "execute_or_queue"

STATUS_RESOLVED = "resolved"
STATUS_PENDING_APPROVAL = "pending_approval"
STATUS_FAILED = "execution_failed"


def _build_summary(state: AgentState) -> str:
    action = state.get("proposed_action")
    order = state.get("retrieved_data")
    if order is not None:
        return f"Proposed '{action}' for order {order.order_id} ({order.product}, amount {order.amount})."
    return f"Proposed '{action}' (no order data involved)."


def _build_citations(state: AgentState) -> str:
    """Evidence backing the proposal, JSON-encoded for the text column."""
    order = state.get("retrieved_data")
    grounding = state.get("validation_results")
    evidence = {
        "order": json.loads(order.model_dump_json()) if order is not None else None,
        "grounding_passed": grounding.result if grounding is not None else None,
        "grounding_reason": grounding.grounding_reason if grounding is not None else None,
    }
    return json.dumps(evidence)


def _set_ticket_status(ticket_id: str, status: str) -> None:
    SupaBase.table("tickets").update({"status": status}).eq("id", ticket_id).execute()

def _queue_for_approval(state: AgentState) -> str:
    ticket_id = state["ticket_id"]
    _set_ticket_status(ticket_id, STATUS_PENDING_APPROVAL)
    try:
        SupaBase.table("pending_actions").insert({
            "ticket_id": ticket_id,
            "proposed_action": state.get("proposed_action") or "escalate_to_human",
            "risk_reason": state.get("risk_reason"),
            "plain_language_summary": _build_summary(state),
            "citations": _build_citations(state),
            "status": "pending",
        }).execute()
    except Exception:
        # Don't leave a ticket marked pending_approval with nothing in the queue.
        try:
            _set_ticket_status(ticket_id, "open")
        except Exception:
            pass
        raise
    return "queued for human approval"

def _auto_execute(state: AgentState) -> str:
    # Mock system: "executing" means closing the ticket. No real payment or
    # email side effects. The audit log below is the record of what happened.
    _set_ticket_status(state["ticket_id"], STATUS_RESOLVED)
    return f"auto-executed '{state.get('proposed_action')}'"


def execute_or_queue(state: AgentState) -> dict:
    ticket_id = state["ticket_id"]
    route = state.get("route")

    try:
        if route == "auto_execute":
            outcome = _auto_execute(state)
        else:
            # Anything that isn't an explicit auto_execute is queued (fail closed).
            outcome = _queue_for_approval(state)
    except Exception as e:
        # The write failed. Log it, mark high risk, and end cleanly.
        reason = "execution_write_failed"
        update = {"ticket_id": ticket_id, "risk_level": "high", "risk_reason": reason}
        try:
            update["decision_log"] = [log_decision(
                ticket_id=ticket_id,
                node_name=_NODE_NAME,
                output_summary=f"{_NODE_NAME} failed while handling route={route}",
                risk_level="high",
                risk_reason=reason,
                raw_trace=repr(e),
                plain_language_rationale="The final write to the database failed; this ticket needs manual attention.",
            )]
        except Exception as log_error:
            print(f"WARNING: {_NODE_NAME} failed AND audit write failed for {ticket_id}: {log_error!r}")
            update["decision_log"] = []
        return update

    update = {"ticket_id": ticket_id}
    try:
        update["decision_log"] = [log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            input_summary=f"route={route}, proposed_action={state.get('proposed_action')}",
            output_summary=outcome,
            risk_level=state.get("risk_level"),
            risk_reason=state.get("risk_reason"),
            plain_language_rationale=f"Final step: {outcome}.",
        )]
    except Exception as log_error:
        # The action already happened; don't undo it, but make the gap visible.
        print(f"WARNING: {_NODE_NAME} succeeded for {ticket_id} but audit write failed: {log_error!r}")
        update["decision_log"] = []
    return update
from db import SupaBase
from audit import log_decision
from state import AgentState


def _log_and_fallback(ticket_id: str, node_name: str, output_summary: str, risk_reason: str) -> dict:
    """Shared helper for the two 'expected' failure paths (query failure, not found).
    Swallows a secondary logging failure to avoid audit-of-audit recursion."""
    try:
        log_decision(
            ticket_id=ticket_id,
            node_name=node_name,
            output_summary=output_summary,
            risk_level="high",
            risk_reason=risk_reason,
            plain_language_rationale=output_summary,
        )
    except Exception:
        pass
    return {"ticket_id": ticket_id, "risk_level": "high", "risk_reason": risk_reason}


def intake(state: AgentState) -> dict:
    """Entry node: looks up the ticket by ticket_id, pulls its message text
    and order_id into state for downstream nodes (classify, retrieve, etc)."""
    ticket_id = state["ticket_id"]

    try:
        response = (
            SupaBase.table("tickets")
            .select("message, order_id, customer_name, status")
            .eq("id", ticket_id)
            .execute()
        )
    except Exception as e:
        return _log_and_fallback(
            ticket_id,
            node_name="intake",
            output_summary=f"intake: query failed ({e!r})",
            risk_reason="ticket_query_failed",
        )

    rows = response.data
    if not rows:
        return _log_and_fallback(
            ticket_id,
            node_name="intake",
            output_summary="intake: ticket_id not found in tickets table",
            risk_reason="ticket_not_found",
        )

    ticket = rows[0]
    ticket_text = ticket.get("message")

    if not ticket_text:
        return _log_and_fallback(
            ticket_id,
            node_name="intake",
            output_summary="intake: ticket found but message field is empty",
            risk_reason="ticket_message_empty",
        )

    # Work succeeded — logging failure here should NOT block intake's return,
    # but it MUST be visible, not silently swallowed.
    try:
        log_decision(
            ticket_id=ticket_id,
            node_name="intake",
            output_summary=f"intake: ticket found, message length={len(ticket_text)}",
            plain_language_rationale="Ticket successfully retrieved and ready for classification.",
        )
    except Exception as log_error:
        print(f"WARNING: intake succeeded for {ticket_id} but audit log write failed: {log_error!r}")

    result = {"ticket_id": ticket_id, "ticket_text": ticket_text}
    if ticket.get("order_id"):
        result["order_id"] = ticket["order_id"]

    return result
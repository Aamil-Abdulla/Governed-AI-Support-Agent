from db import SupaBase
from audit import log_decision
from schemas import OrderRecord
from state import AgentState

_NODE_NAME = "retrieve"

# Ticket types where an order is expected to exist — if order_id is missing
# or the lookup fails for these, that's a real problem, not a normal case.
_REQUIRES_ORDER = {"refund_request", "order_status"}


def retrieve(state: AgentState) -> dict:
    ticket_id = state["ticket_id"]
    order_id = state.get("order_id")
    classification_report = state.get("classification_report")


    existing_risk_level = state.get("risk_level")
    existing_risk_reason = state.get("risk_reason")

    ticket_type = classification_report.ticket_type if classification_report else None
    order_required = ticket_type in _REQUIRES_ORDER


    if order_required and not order_id:
        reason = "order_required_but_missing_order_id"
        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            output_summary=f"ticket_type={ticket_type} requires an order but no order_id present",
            risk_level="high",
            risk_reason=reason,
            plain_language_rationale=(
                f"This ticket was classified as '{ticket_type}', which needs an order on file, "
                "but no order ID was provided, so no order could be looked up."
            ),
        )
        return {
            "ticket_id": ticket_id,
            "retrieved_data": None,
            "risk_level": existing_risk_level or "high",
            "risk_reason": existing_risk_reason or reason,
            "decision_log": [decision],
        }


    if not order_id:
        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            output_summary=f"ticket_type={ticket_type} does not require an order; skipping retrieval",
            risk_level=existing_risk_level or "low",
            risk_reason=existing_risk_reason,
            plain_language_rationale=f"Ticket type '{ticket_type}' does not require order data.",
        )
        return {
            "ticket_id": ticket_id,
            "retrieved_data": None,
            "risk_level": existing_risk_level or "low",
            "risk_reason": existing_risk_reason,
            "decision_log": [decision],
        }


    try:
        rows = (
            SupaBase.table("mock_orders")
            .select("*")
            .eq("order_id", order_id)
            .execute()
            .data
        )
    except Exception as e:
        reason = "supabase_query_failed"
        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            output_summary=f"Supabase query failed for order_id={order_id}",
            risk_level="high",
            risk_reason=reason,
            raw_trace=repr(e),
            plain_language_rationale="The order lookup failed due to a database error.",
        )
        return {
            "ticket_id": ticket_id,
            "retrieved_data": None,
            "risk_level": "high",
            "risk_reason": reason,
            "decision_log": [decision],
        }


    if not rows:
        if order_required:
            reason = "order_not_found_for_required_type"
            risk_level = "high"
        else:
            reason = "order_not_found_but_not_required"
            risk_level = existing_risk_level or "low"

        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            output_summary=f"No order found for order_id={order_id}",
            risk_level=risk_level,
            risk_reason=reason,
            plain_language_rationale=f"No matching order was found for order_id '{order_id}'.",
        )
        return {
            "ticket_id": ticket_id,
            "retrieved_data": None,
            "risk_level": risk_level,
            "risk_reason": reason,
            "decision_log": [decision],
        }

    try:
        order_record = OrderRecord(**rows[0])
    except Exception as e:
        reason = "order_record_validation_failed"
        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            output_summary=f"Order row for order_id={order_id} failed schema validation",
            risk_level="high",
            risk_reason=reason,
            raw_trace=repr(e),
            plain_language_rationale="The order record found did not match the expected structure.",
        )
        return {
            "ticket_id": ticket_id,
            "retrieved_data": None,
            "risk_level": "high",
            "risk_reason": reason,
            "decision_log": [decision],
        }


    decision = log_decision(
        ticket_id=ticket_id,
        node_name=_NODE_NAME,
        output_summary=f"Order {order_id} retrieved successfully",
        risk_level=existing_risk_level or "low",
        risk_reason=existing_risk_reason,
        plain_language_rationale=f"Order '{order_id}' was found and validated successfully.",
    )
    return {
        "ticket_id": ticket_id,
        "retrieved_data": order_record,
        "risk_level": existing_risk_level or "low",
        "risk_reason": existing_risk_reason,
        "decision_log": [decision],
    }
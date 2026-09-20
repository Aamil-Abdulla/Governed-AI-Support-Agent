from audit import log_decision
from state import AgentState

_NODE_NAME = "propose_action"


def _propose(ticket_id, action, default_risk, existing_risk_level, risk_reason, summary, rationale):
    """Log the proposal and build the state update. Never downgrades an existing risk flag."""
    risk_level = existing_risk_level or default_risk
    decision = log_decision(
        ticket_id=ticket_id,
        node_name=_NODE_NAME,
        output_summary=summary,
        risk_level=risk_level,
        risk_reason=risk_reason,
        plain_language_rationale=rationale,
    )
    return {
        "ticket_id": ticket_id,
        "proposed_action": action,
        "risk_level": risk_level,
        "risk_reason": risk_reason,
        "decision_log": [decision],
    }


def propose_action(state: AgentState) -> dict:
    ticket_id = state["ticket_id"]
    classification_report = state.get("classification_report")
    order = state.get("retrieved_data")
    existing_risk_level = state.get("risk_level")
    existing_risk_reason = state.get("risk_reason")

    def propose(action, default_risk, summary, rationale, risk_reason=existing_risk_reason):
        return _propose(ticket_id, action, default_risk, existing_risk_level, risk_reason, summary, rationale)

    # Classification never completed: we cannot know what this ticket needs.
    if classification_report is None:
        return propose(
            "escalate_to_human", "high",
            "classification_report missing — cannot determine if order lookup was needed",
            "Classification did not complete for this ticket, so it could not be "
            "determined whether an order needed to be looked up.",
            risk_reason=existing_risk_reason or "classification_report_missing",
        )

    ticket_type = classification_report.ticket_type

    # --- Policy table: ticket_type + retrieved_data -> proposed_action ---
    if ticket_type == "refund_request":
        if order is None:
            return propose("escalate_to_human", "high", "Proposing action: escalate_to_human",
                           "The ticket is a refund request but no order data was retrieved.")
        if order.refund_eligible:
            return propose("issue_refund", "low", "Proposing action: issue_refund",
                           "The ticket is a refund request and the order is eligible for a refund.")
        return propose("deny_refund", "low", "Proposing action: deny_refund",
                       "The ticket is a refund request but the order is not eligible for a refund.")

    if ticket_type == "order_status":
        if order is None:
            return propose("escalate_to_human", "high", "Proposing action: escalate_to_human",
                           "The ticket is an order status inquiry but no order data was retrieved.")
        return propose("provide_order_status", "low", "Proposing action: provide_order_status",
                       "The ticket is an order status inquiry and order data was retrieved.")

    if ticket_type == "product_question":
        return propose("answer_product_question", "low", "Proposing action: answer_product_question",
                       "The ticket is a product question.")

    if ticket_type in ("complaint", "other"):
        return propose("escalate_to_human", "medium", "Proposing action: escalate_to_human",
                       "The ticket is a complaint or other type, which requires human review.")

    # Unreachable in practice (Literal typing), but fail safe and leave a trace.
    return propose(
        "escalate_to_human", "medium",
        "Proposing action: escalate_to_human (unmatched ticket_type)",
        "ticket_type did not match any known policy branch — this should not be "
        "possible and indicates an unexpected state.",
        risk_reason=existing_risk_reason or "unmatched_ticket_type",
    )
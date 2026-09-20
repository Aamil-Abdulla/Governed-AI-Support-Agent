from decimal import Decimal

from audit import log_decision
from state import AgentState

_NODE_NAME = "decide"

# Above this refund amount, a human must approve.
REFUND_AUTO_LIMIT = Decimal("100")

# Actions that are safe to run without a human, when grounded and low risk.
_AUTO_ELIGIBLE = {"issue_refund", "deny_refund", "provide_order_status", "answer_product_question"}


def _decide_route(state: AgentState) -> tuple[str, str]:
    """Returns (route, explanation). Default is require_approval; auto_execute
    must be earned by passing every check."""
    action = state.get("proposed_action")
    grounding = state.get("validation_results")
    risk_level = state.get("risk_level")
    order = state.get("retrieved_data")

    if action is None or grounding is None:
        return "require_approval", "Missing proposed action or grounding result."

    if not grounding.result:
        return "require_approval", f"Grounding failed ({grounding.grounding_reason})."

    if action not in _AUTO_ELIGIBLE:
        return "require_approval", f"Action '{action}' always needs a human."

    if risk_level != "low":
        return "require_approval", f"Risk level is '{risk_level}', not low."

    if action == "issue_refund":
        if order is None:
            return "require_approval", "Refund proposed but no order data available."
        if order.amount > REFUND_AUTO_LIMIT:
            return (
                "require_approval",
                f"Refund amount {order.amount} exceeds auto-approve limit {REFUND_AUTO_LIMIT}.",
            )

    return "auto_execute", "Grounded, low risk, and within policy limits."


def decide(state: AgentState) -> dict:
    ticket_id = state["ticket_id"]
    route, explanation = _decide_route(state)

    update = {"ticket_id": ticket_id, "route": route}

    try:
        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            input_summary=f"proposed_action={state.get('proposed_action')}, risk={state.get('risk_level')}",
            output_summary=f"route={route}",
            risk_level=state.get("risk_level"),
            risk_reason=state.get("risk_reason"),
            plain_language_rationale=explanation,
        )
        update["decision_log"] = [decision]
    except Exception as log_error:
        print(f"WARNING: decide audit write failed for {ticket_id}: {log_error!r}")
        # Fail closed: if we can't audit the decision, don't auto-execute it.
        update["route"] = "require_approval"
        update["risk_level"] = "high"
        update["risk_reason"] = "audit_logging_failure"
        update["decision_log"] = []

    return update
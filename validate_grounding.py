from datetime import date

from audit import log_decision
from schemas import GroundingResult
from state import AgentState

_NODE_NAME = "validate_grounding"

REFUND_WINDOW_DAYS = 30

_NEEDS_ORDER = {"issue_refund", "deny_refund", "provide_order_status"}
_NO_EVIDENCE_NEEDED = {"answer_product_question", "escalate_to_human"}


def _check_grounding(proposed_action: str, order, ticket_order_id: str | None) -> tuple[bool, str | None, str]:
    """Pure fact-check. Returns (passed, failure_reason, explanation)."""
    if proposed_action in _NO_EVIDENCE_NEEDED:
        return True, None, f"'{proposed_action}' requires no order evidence."

    if proposed_action not in _NEEDS_ORDER:
        # Unknown action: refuse to vouch for it.
        return False, "field_mismatch", f"Unknown proposed action '{proposed_action}'."

    if order is None:
        return False, "order_not_found", f"'{proposed_action}' requires order data but none was retrieved."

    # The order we retrieved must be the order the ticket referenced.
    if ticket_order_id and order.order_id != ticket_order_id:
        return (
            False,
            "field_mismatch",
            f"Retrieved order '{order.order_id}' does not match ticket order '{ticket_order_id}'.",
        )

    if proposed_action == "issue_refund":
        if not order.refund_eligible:
            return False, "field_mismatch", "issue_refund proposed but the order is not refund-eligible."
        age_days = (date.today() - order.purchase_date).days
        if age_days > REFUND_WINDOW_DAYS:
            return (
                False,
                "stale_data",
                f"Order is {age_days} days old, outside the {REFUND_WINDOW_DAYS}-day refund window.",
            )
        return True, None, f"Order is eligible and {age_days} days old, within the refund window."

    if proposed_action == "deny_refund":
        if order.refund_eligible:
            return False, "field_mismatch", "deny_refund proposed but the order is actually refund-eligible."
        return True, None, "Order is not refund-eligible, so denial is supported."

    # provide_order_status: order exists and matches, that's enough.
    return True, None, "Order found and matches the ticket."


def validate_grounding(state: AgentState) -> dict:
    ticket_id = state["ticket_id"]
    proposed_action = state.get("proposed_action")
    order = state.get("retrieved_data")
    ticket_order_id = state.get("order_id")
    existing_risk_level = state.get("risk_level")
    existing_risk_reason = state.get("risk_reason")

    # No proposed action means propose_action never ran or failed. Fail closed.
    if proposed_action is None:
        result = GroundingResult(
            result=False,
            grounding_reason="field_mismatch",
            pre_grounding_proposed_action="none",
        )
        explanation = "No proposed_action in state; cannot validate."
        passed = False
    else:
        passed, reason, explanation = _check_grounding(proposed_action, order, ticket_order_id)
        result = GroundingResult(
            result=passed,
            grounding_reason=reason,
            pre_grounding_proposed_action=proposed_action,
        )

    # Never downgrade a pre-existing risk flag; failed grounding forces high.
    if passed:
        risk_level = existing_risk_level or "low"
        risk_reason = existing_risk_reason
    else:
        risk_level = "high"
        risk_reason = f"grounding_failed:{result.grounding_reason}"

    update = {
        "ticket_id": ticket_id,
        "validation_results": result,
        "risk_level": risk_level,
        "risk_reason": risk_reason,
    }
    # On failure, the safe action is a human. Record the override in the log below.
    if not passed:
        update["proposed_action"] = "escalate_to_human"

    try:
        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            input_summary=f"proposed_action={proposed_action}",
            output_summary=(
                "grounding passed"
                if passed
                else f"grounding failed ({result.grounding_reason}); overriding to escalate_to_human"
            ),
            risk_level=risk_level,
            risk_reason=risk_reason,
            plain_language_rationale=explanation,
        )
        update["decision_log"] = [decision]
    except Exception as log_error:
        # Audit failure: fail closed. Force high risk and escalate.
        print(f"WARNING: validate_grounding audit write failed for {ticket_id}: {log_error!r}")
        update["risk_level"] = "high"
        update["risk_reason"] = "audit_logging_failure"
        update["proposed_action"] = "escalate_to_human"
        update["decision_log"] = []

    return update
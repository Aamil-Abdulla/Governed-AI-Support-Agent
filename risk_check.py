from decimal import Decimal

from audit import log_decision
from state import AgentState

_NODE_NAME = "risk_check"

# Kept in sync with decide.py on purpose: risk_check is an independent
# second gate, so it re-checks limits itself instead of trusting `route`.
REFUND_AUTO_LIMIT = Decimal("100")


def _find_problems(state: AgentState) -> list[str]:
    """Returns a list of reasons auto-execution is unsafe. Empty list = safe."""
    problems = []
    action = state.get("proposed_action")
    grounding = state.get("validation_results")
    risk_level = state.get("risk_level")
    order = state.get("retrieved_data")

    if action is None:
        problems.append("no_proposed_action")
    if action == "escalate_to_human":
        problems.append("action_requires_human")
    if grounding is None or not grounding.result:
        problems.append("grounding_missing_or_failed")
    if risk_level != "low":
        problems.append(f"risk_level_{risk_level}")
    if action == "issue_refund":
        if order is None:
            problems.append("refund_without_order")
        elif order.amount > REFUND_AUTO_LIMIT:
            problems.append("refund_over_limit")
    return problems


def risk_check(state: AgentState) -> dict:
    ticket_id = state["ticket_id"]
    route = state.get("route")

    # Only auto_execute needs re-checking. A route that is already
    # require_approval (or missing) is never loosened here.
    if route != "auto_execute":
        final_route = "require_approval"
        problems: list[str] = []
        explanation = f"Route was '{route}'; no auto-execution to gate."
    else:
        problems = _find_problems(state)
        if problems:
            final_route = "require_approval"
            explanation = "Auto-execution blocked by independent check: " + ", ".join(problems)
        else:
            final_route = "auto_execute"
            explanation = "Independent check confirmed auto-execution is safe."

    update = {"ticket_id": ticket_id, "route": final_route}
    if problems:
        update["risk_level"] = "high" if state.get("risk_level") == "high" else "medium"
        update["risk_reason"] = state.get("risk_reason") or f"risk_check_blocked:{problems[0]}"

    try:
        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            input_summary=f"incoming route={route}",
            output_summary=f"final route={final_route}",
            risk_level=update.get("risk_level", state.get("risk_level")),
            risk_reason=update.get("risk_reason", state.get("risk_reason")),
            plain_language_rationale=explanation,
        )
        update["decision_log"] = [decision]
    except Exception as log_error:
        print(f"WARNING: risk_check audit write failed for {ticket_id}: {log_error!r}")
        update["route"] = "require_approval"
        update["risk_level"] = "high"
        update["risk_reason"] = "audit_logging_failure"
        update["decision_log"] = []

    return update
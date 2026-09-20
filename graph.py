from langgraph.graph import StateGraph, END

from state import AgentState
from intake import intake
from classify import classify
from retrieve import retrieve
from propose_action import propose_action
from validate_grounding import validate_grounding
from decide import decide
from risk_check import risk_check
from execute_or_queue import execute_or_queue

# risk_reasons from intake that mean the ticket row does not exist, so
# nothing downstream (pending_actions has a FK to tickets) can succeed.
_TICKET_MISSING_REASONS = {"ticket_not_found", "ticket_query_failed"}


def _after_intake(state: AgentState) -> str:
    if state.get("risk_reason") in _TICKET_MISSING_REASONS:
        return "end"
    return "classify"


def _after_decide(state: AgentState) -> str:
    if state.get("route") == "auto_execute":
        return "risk_check"
    return "execute_or_queue"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("intake", intake)
    graph.add_node("classify", classify)
    graph.add_node("retrieve", retrieve)
    graph.add_node("propose_action", propose_action)
    graph.add_node("validate_grounding", validate_grounding)
    graph.add_node("decide", decide)
    graph.add_node("risk_check", risk_check)
    graph.add_node("execute_or_queue", execute_or_queue)

    graph.set_entry_point("intake")
    graph.add_conditional_edges("intake", _after_intake, {"classify": "classify", "end": END})
    graph.add_edge("classify", "retrieve")
    graph.add_edge("retrieve", "propose_action")
    graph.add_edge("propose_action", "validate_grounding")
    graph.add_edge("validate_grounding", "decide")
    graph.add_conditional_edges(
        "decide", _after_decide,
        {"risk_check": "risk_check", "execute_or_queue": "execute_or_queue"},
    )
    graph.add_edge("risk_check", "execute_or_queue")
    graph.add_edge("execute_or_queue", END)

    return graph.compile()


def run_ticket(ticket_id: str) -> dict:
    """Run one ticket through the full pipeline and return the final state."""
    app = build_graph()
    return app.invoke({"ticket_id": ticket_id, "decision_log": []})


if __name__ == "__main__":
    import sys
    result = run_ticket(sys.argv[1])
    print(f"proposed_action: {result.get('proposed_action')}")
    print(f"route:           {result.get('route')}")
    print(f"risk_level:      {result.get('risk_level')} ({result.get('risk_reason')})")
    print(f"decisions logged: {len(result['decision_log'])}")
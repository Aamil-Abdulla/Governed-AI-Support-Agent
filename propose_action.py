from state import AgentState
from audit import log_decision
_NODE_NAME = "propose_action"

def propose_action(state:AgentState):
    classification_report = state.get("classification_report")
    retrieved_data=state.get("retrieved_data")
    existing_risk_level = state.get("risk_level")
    existing_risk_reason = state.get("risk_reason")
    ticket_id = state["ticket_id"]

    if classification_report is None:
        ticket_id = ticket_id
        reason = existing_risk_reason or "classification_report_missing"
        descision = log_decision(
            ticket_id=ticket_id,
            node_name="propose_action",
            output_summary="classification_report missing — cannot determine if order lookup was needed",
            risk_level=existing_risk_level or "high",
            risk_reason=reason,
            plain_language_rationale=(
                "Classification did not complete for this ticket, so it could not be "
                "determined whether an order needed to be looked up."
            ),

        )
        return {
            "ticket_id": ticket_id,
            "proposed_action": "escalate_to_human",
            "risk_level": existing_risk_level or "high",
            "risk_reason": reason,
            "decision_log": [descision],
        }
    
    ticket_type = classification_report.ticket_type



#Case 1 : if ticket_type exist and eligible , then proposing action as issue refund
    if ticket_type == "refund_request" and retrieved_data is not None and retrieved_data.refund_eligible:
        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            output_summary="Proposing action: issue_refund",
            risk_level=existing_risk_level or "low",
            risk_reason=existing_risk_reason,
            plain_language_rationale="The ticket is a refund request and the order is eligible for a refund."
        )
        return {
            "ticket_id": ticket_id,
            "proposed_action": "issue_refund",
            "risk_level": existing_risk_level or "low",
            "risk_reason": existing_risk_reason,
            "decision_log": [decision],
        }

    if ticket_type == "refund_request" and retrieved_data is not None and not retrieved_data.refund_eligible:
        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            output_summary="Proposing action: deny_refund",
            risk_level=existing_risk_level or "low",
            risk_reason=existing_risk_reason,
            plain_language_rationale="The ticket is a refund request but the order is not eligible for a refund."
        )
        return {
            "ticket_id": ticket_id,
            "proposed_action": "deny_refund",
            "risk_level": existing_risk_level or "low",
            "risk_reason": existing_risk_reason,
            "decision_log": [decision],
        }

    if ticket_type=="refund_request" and retrieved_data is None:
        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            output_summary="Proposing action: escalate_to_human",
            risk_level=existing_risk_level or "high",
            risk_reason=existing_risk_reason,
            plain_language_rationale="The ticket is a refund request but no order data was retrieved."
        )
        return {
            "ticket_id": ticket_id,
            "proposed_action": "escalate_to_human",
            "risk_level": existing_risk_level or "high",
            "risk_reason": existing_risk_reason,
            "decision_log": [decision],
        }

    if ticket_type == "order_status" and retrieved_data is not None:
        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            output_summary="Proposing action: provide_order_status",
            risk_level=existing_risk_level or "low",
            risk_reason=existing_risk_reason,
            plain_language_rationale="The ticket is an order status inquiry and order data was retrieved."
        )
        return {
            "ticket_id": ticket_id,
            "proposed_action": "provide_order_status",
            "risk_level": existing_risk_level or "low",
            "risk_reason": existing_risk_reason,
            "decision_log": [decision],
        }

    if ticket_type == "order_status" and retrieved_data is None:
        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            output_summary="Proposing action: escalate_to_human",
            risk_level=existing_risk_level or "high",
            risk_reason=existing_risk_reason,
            plain_language_rationale="The ticket is an order status inquiry but no order data was retrieved."
        )
        return {
            "ticket_id": ticket_id,
            "proposed_action": "escalate_to_human",
            "risk_level": existing_risk_level or "high",
            "risk_reason": existing_risk_reason,
            "decision_log": [decision],
        }

    if ticket_type=="product_question":
        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            output_summary="Proposing action: answer_product_question",
            risk_level=existing_risk_level or "low",
            risk_reason=existing_risk_reason,
            plain_language_rationale="The ticket is a product question."
        )
        return {
            "ticket_id": ticket_id,
            "proposed_action": "answer_product_question",
            "risk_level": existing_risk_level or "low",
            "risk_reason": existing_risk_reason,
            "decision_log": [decision],
        }

    if ticket_type in ["complaint", "other"]:
        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            output_summary="Proposing action: escalate_to_human",
            risk_level=existing_risk_level or "medium",
            risk_reason=existing_risk_reason,
            plain_language_rationale="The ticket is a complaint or other type, which requires human review."
        )
        return {
            "ticket_id": ticket_id,
            "proposed_action": "escalate_to_human",
            "risk_level": existing_risk_level or "medium",
            "risk_reason": existing_risk_reason,
            "decision_log": [decision],
        }
    else:
        decision = log_decision(
            ticket_id=ticket_id,
            node_name=_NODE_NAME,
            output_summary="Proposing action: escalate_to_human (unmatched ticket_type)",
            risk_level=existing_risk_level or "medium",
            risk_reason=existing_risk_reason or "unmatched_ticket_type",
            plain_language_rationale=(
                "ticket_type did not match any known policy branch — this should not be "
                "possible and indicates an unexpected state."
            ),
    )
        return {
            "ticket_id": ticket_id,
            "proposed_action": "escalate_to_human",
            "risk_level": existing_risk_level or "medium",
            "risk_reason": existing_risk_reason or "unmatched_ticket_type",
            "decision_log": [decision],
    }
    
    
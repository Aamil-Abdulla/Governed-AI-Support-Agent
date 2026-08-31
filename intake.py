from db import SupaBase
from audit import log_decision

def intake(
ticket_id: str
) -> dict:
    try:
        filtered_dict=(SupaBase.table("tickets").select("*").eq("id",ticket_id).execute())
        ticket = filtered_dict.data[0]
        log_decision(
            ticket_id=ticket_id,
            node_name="intake",
            input_summary=f"Customer Name: {ticket['customer_name']}, Message: {ticket['message']}, Order ID: {ticket['order_id']}",
            output_summary="Ticket data inserted successfully.",
            source_retrieved=None,
            tool_called=None,
            parameters={"customer_name": ticket["customer_name"], "message": ticket["message"], "order_id": ticket["order_id"]},
            risk_score=None,
            raw_trace=None,
            plain_language_rationale="Intake node processed the ticket data."
        )
        return {
            "customer_name": ticket["customer_name"],
            "message": ticket["message"],
            "order_id": ticket["order_id"]
        }
    except Exception as e:
        print(f"[intake] Failed to Insert the ticket data for the customer")

    
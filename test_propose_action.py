from schemas import ClassificationReport, OrderRecord
from propose_action import propose_action
from state import AgentState
from datetime import date
from decimal import Decimal

# Reuse real ticket UUIDs from your tickets table — decisions.ticket_id is a
# foreign key into tickets.id, so made-up strings like "test-1" will fail
# the insert (wrong type / no matching row).
TICKET_ID_1 = "34efc221-d72b-4dee-baf1-5b61e66ae3c4"
TICKET_ID_2 = "1277aa7c-1a62-4a75-a486-1260246ca59c"
TICKET_ID_3 = "63582bd9-dc80-44a3-bc54-843ae42996e7"
TICKET_ID_4 = "7ec0e581-4809-46e4-9704-da341b9f7027"
TICKET_ID_5 = "c1b63a68-aab5-4d05-b028-84716b65da4b"


def run_case(name: str, state: AgentState):
    print(f"\n{'=' * 60}")
    print(f"CASE: {name}")
    print(f"{'=' * 60}")
    try:
        result = propose_action(state)
        for k, v in result.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"\n!!! CRASHED: {e!r}")


def make_order(refund_eligible: bool) -> OrderRecord:
    return OrderRecord(
        order_id="ORDER123",
        customer_name="Test User",
        product="Widget",
        amount=Decimal("50.00"),
        purchase_date=date(2025, 1, 1),
        refund_eligible=refund_eligible,
        refund_ineligible_reason=None if refund_eligible else "past_return_window",
    )


def main():
    # Case 1: refund_request, eligible → issue_refund
    run_case(
        "Refund request, eligible",
        {
            "ticket_id": TICKET_ID_1,
            "classification_report": ClassificationReport(
                ticket_type="refund_request", confidence=0.9
            ),
            "retrieved_data": make_order(refund_eligible=True),
        },
    )

    # Case 2: refund_request, ineligible → deny_refund
    run_case(
        "Refund request, ineligible",
        {
            "ticket_id": TICKET_ID_5,
            "classification_report": ClassificationReport(
                ticket_type="refund_request", confidence=0.9
            ),
            "retrieved_data": make_order(refund_eligible=False),
        },
    )

    # Case 3: refund_request, no retrieved data → escalate_to_human
    run_case(
        "Refund request, no retrieved data",
        {
            "ticket_id": TICKET_ID_1,
            "classification_report": ClassificationReport(
                ticket_type="refund_request", confidence=0.9
            ),
            "retrieved_data": None,
        },
    )

    # Case 4: order_status, data present → provide_order_status
    run_case(
        "Order status, retrieved data present",
        {
            "ticket_id": TICKET_ID_4,
            "classification_report": ClassificationReport(
                ticket_type="order_status", confidence=0.8
            ),
            "retrieved_data": make_order(refund_eligible=True),
        },
    )

    # Case 5: order_status, no data → escalate_to_human
    run_case(
        "Order status, no retrieved data",
        {
            "ticket_id": TICKET_ID_5,
            "classification_report": ClassificationReport(
                ticket_type="order_status", confidence=0.8
            ),
            "retrieved_data": None,
        },
    )

    # Case 6: complaint → escalate_to_human
    run_case(
        "Complaint ticket type",
        {
            "ticket_id": TICKET_ID_2,
            "classification_report": ClassificationReport(
                ticket_type="complaint", confidence=0.85
            ),
            "retrieved_data": None,
        },
    )

    # Case 7: other → escalate_to_human
    run_case(
        "Other ticket type",
        {
            "ticket_id": TICKET_ID_3,
            "classification_report": ClassificationReport(
                ticket_type="other", confidence=0.75
            ),
            "retrieved_data": None,
        },
    )

    # Case 8: product_question → answer_product_question
    run_case(
        "Product question",
        {
            "ticket_id": TICKET_ID_2,
            "classification_report": ClassificationReport(
                ticket_type="product_question", confidence=0.9
            ),
            "retrieved_data": None,
        },
    )

    # Case 9: classification_report is None → escalate_to_human, risk stays high
    run_case(
        "Classification missing, no pre-existing risk",
        {
            "ticket_id": TICKET_ID_3,
            "classification_report": None,
            "retrieved_data": None,
        },
    )

    # Case 9b: classification_report is None, pre-existing high risk from classify
    # failure — confirms this branch preserves it rather than resetting it
    run_case(
        "Classification missing, pre-existing high risk preserved",
        {
            "ticket_id": TICKET_ID_4,
            "classification_report": None,
            "retrieved_data": None,
            "risk_level": "high",
            "risk_reason": "classification_failed",
        },
    )


if __name__ == "__main__":
    main()
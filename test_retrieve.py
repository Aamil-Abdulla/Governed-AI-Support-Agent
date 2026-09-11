"""
Standalone test script for retrieve.py — no LangGraph, no pytest.
Just calls retrieve() directly with hand-built state dicts and prints results.

Before running:
1. Make sure your .env is set up and Supabase is reachable.
2. In your mock_orders table, confirm at least one order_id exists so you can
   plug it into VALID_ORDER_ID below. Use an order_id that does NOT exist for
   the "not found" case.
3. Run with: python test_retrieve.py
"""

from schemas import ClassificationReport
from retrieve import retrieve

# --- EDIT THESE to match real rows in your mock_orders table ---
VALID_ORDER_ID = "ORDER123"       # must exist in mock_orders
NONEXISTENT_ORDER_ID = "NOPE999"  # must NOT exist in mock_orders
# -----------------------------------------------------------------

# decisions.ticket_id has a foreign key constraint against tickets.id, so
# these must be real rows that exist in the tickets table (not random UUIDs).
TICKET_ID_1 = "34efc221-d72b-4dee-baf1-5b61e66ae3c4"  # Alice Johnson - refund for mouse
TICKET_ID_2 = "1277aa7c-1a62-4a75-a486-1260246ca59c"  # Dana Lee - USB-C hub question
TICKET_ID_3 = "63582bd9-dc80-44a3-bc54-843ae42996e7"  # Alice Johnson - where is my order
TICKET_ID_4 = "7ec0e581-4809-46e4-9704-da341b9f7027"  # Eli Park - order status please
TICKET_ID_5 = "c1b63a68-aab5-4d05-b028-84716b65da4b"  # Test User - refund for jacket


def run_case(name: str, state: dict):
    print(f"\n{'=' * 60}")
    print(f"CASE: {name}")
    print(f"{'=' * 60}")
    print(f"Input state: {state}")
    try:
        result = retrieve(state)
        print(f"\nResult:")
        for k, v in result.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"\n!!! CRASHED: {e!r}")


def main():
    # Case 1: order required (refund_request) but no order_id at all
    run_case(
        "Order required, missing order_id",
        {
            "ticket_id": TICKET_ID_1,
            "order_id": None,
            "classification_report": ClassificationReport(
                ticket_type="refund_request", confidence=0.9
            ),
        },
    )

    # Case 2: order not required (product_question), no order_id
    run_case(
        "Order not required, no order_id",
        {
            "ticket_id": TICKET_ID_2,
            "order_id": None,
            "classification_report": ClassificationReport(
                ticket_type="product_question", confidence=0.85
            ),
        },
    )

    # Case 3: valid order_id that exists in mock_orders
    run_case(
        "Valid order_id, should be found",
        {
            "ticket_id": TICKET_ID_3,
            "order_id": VALID_ORDER_ID,
            "classification_report": ClassificationReport(
                ticket_type="refund_request", confidence=0.95
            ),
        },
    )

    # Case 4: order_id given but doesn't exist in the table, and IS required
    run_case(
        "order_id given but not found, required type",
        {
            "ticket_id": TICKET_ID_4,
            "order_id": NONEXISTENT_ORDER_ID,
            "classification_report": ClassificationReport(
                ticket_type="order_status", confidence=0.8
            ),
        },
    )

    # Case 5: classification missing entirely (upstream classify failure
    # scenario) — also check that a pre-existing high risk is preserved.
    run_case(
        "No classification_report + pre-existing high risk from classify failure",
        {
            "ticket_id": TICKET_ID_5,
            "order_id": None,
            "classification_report": None,
            "risk_level": "high",
            "risk_reason": "classification_failed",
        },
    )


if __name__ == "__main__":
    main()

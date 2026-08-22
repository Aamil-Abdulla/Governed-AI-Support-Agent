from datetime import date
from typing import Literal
from decimal import Decimal
from pydantic import BaseModel



class OrderRecord(BaseModel):
    order_id: str
    customer_name: str
    product: str
    amount: Decimal
    purchase_date : date
    refund_eligible: bool
    refund_ineligible_reason: str | None

GroundingFailureReason = Literal[
"stale_data" , "order_not_found" , "field_mismatch"]

class GroundingResult(BaseModel):
    result: bool
    grounding_reason: GroundingFailureReason
    pre_grounding_proposed_action: str


class ClassificationReport(BaseModel):
    ticket_type: Literal[
        "refund_request", "order_status", "product_question", "complaint", "other"
    ]
    confidence: float
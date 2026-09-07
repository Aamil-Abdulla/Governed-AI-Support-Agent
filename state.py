from typing import NotRequired, TypedDict
from schemas import OrderRecord, GroundingResult, ClassificationReport, Route
import operator
from typing_extensions import Annotated

class AgentState(TypedDict):
    # 1. Input
    ticket_id: str
    ticket_text: NotRequired[str]
    order_id: NotRequired[str]
    # 2. Per node results (progressively filled in, so NotRequired)
    classification_report: NotRequired[ClassificationReport]
    retrieved_data: NotRequired[OrderRecord]
    validation_results: NotRequired[GroundingResult]
    risk_level: NotRequired[str]
    risk_reason: NotRequired[str]
    proposed_action: NotRequired[str]
    # 3. Accumulating
    decision_log: Annotated[list[dict], operator.add]
    # 4. Routing / Final
    route: NotRequired[Route]
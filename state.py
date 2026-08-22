from typing import  NotRequired, TypedDict
from schemas import OrderRecord, GroundingResult,ClassificationReport
import operator
from typing_extensions import Annotated, 

class AgentState(TypedDict):
    #1.Input
    ticket_id: str
    order_id: NotRequired[str]
    #2.Per node results
    classification_report: ClassificationReport
    retrieved_data: OrderRecord
    validation_results: GroundingResult
    risk_level: str
    proposed_action: str
    #3. Accumulating
    decision_log: Annotated[list[dict],operator.add]
    #4. Routing / Final
    route: str



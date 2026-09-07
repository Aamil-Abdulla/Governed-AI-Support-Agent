import json
from audit import log_decision
from schemas import ClassificationReport
from state import AgentState
from openai import AzureOpenAI, APIError, APITimeout, RateLimitError
from pydantic import ValidationError



def classify_ticket(state: AgentState) -> dict:





    return {"ticket_id": ticket_id,}
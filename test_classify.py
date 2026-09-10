import uuid
from db import SupaBase
from intake import intake
from classify import classify

ticket_id = str(uuid.uuid4())
SupaBase.table("tickets").insert({
    "id": ticket_id,
    "customer_name": "Test User",
    "message": "I want a refund for my damaged jacket.",
}).execute()

state = {"ticket_id": ticket_id}
state.update(intake(state))
print("after intake:", state)

state.update(classify(state))
print("after classify:", state)
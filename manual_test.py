from classify import classify

state = {"ticket_id": "test-real-1", "ticket_text": "Where is my order? It's been 2 weeks and I haven't received it."}
result = classify(state)
print(result)
from audit import log_decision
def _log_and_fallback(ticket_id: str, node_name: str, output_summary: str, risk_reason: str) -> dict:
    """Shared helper for the two 'expected' failure paths (query failure, not found).
    Swallows a secondary logging failure to avoid audit-of-audit recursion."""
    try:
        log_decision(
            ticket_id=ticket_id,
            node_name=node_name,
            output_summary=output_summary,
            risk_level="high",
            risk_reason=risk_reason,
            plain_language_rationale=output_summary,
        )
    except Exception:
        pass
    return {"ticket_id": ticket_id, "risk_level": "high", "risk_reason": risk_reason}
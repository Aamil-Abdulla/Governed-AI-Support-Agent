from db import SupaBase
 
 
def log_decision(
    ticket_id: str,
    node_name: str,
    input_summary: str | None = None,
    output_summary: str | None = None,
    source_retrieved: str | None = None,
    tool_called: str | None = None,
    parameters: dict | None = None,
    risk_score: float | None = None,
    risk_level: str | None = None,
    risk_reason: str | None = None,
    raw_trace: str | None = None,
    plain_language_rationale: str | None = None,
) -> dict:
    """
    Fail-safe, not fail-open.
 
    Primary path: insert the full decision row, return that same record
    (as a dict) so callers can accumulate it into state.decision_log
    without a second round-trip to Supabase.
 
    On primary failure: attempt one last-resort minimal write, tagging
    node_name with a sentinel suffix so it's clearly audit.py reporting
    on itself, not a node misrepresenting which node it is. Return that
    minimal record on success.
 
    If even the minimal write fails: swallow and re-raise, so the
    calling node's own isolated try/except around log_decision(...) can
    catch it and fall back (risk_level="high", risk_reason="audit_logging_failure").
    """
    record = {
        "ticket_id": ticket_id,
        "node_name": node_name,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "source_retrieved": source_retrieved,
        "tool_called": tool_called,
        "parameters": parameters,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_reason": risk_reason,
        "raw_trace": raw_trace,
        "plain_language_rationale": plain_language_rationale,
    }
 
    try:
        SupaBase.table("decisions").insert(record).execute()
        return record
    except Exception as primary_error:
        primary_error_msg = repr(primary_error)
 
    fallback_record = {
        "ticket_id": ticket_id,
        "node_name": f"{node_name}__LOGGING_FAILED",
        "raw_trace": primary_error_msg,
    }
    try:
        SupaBase.table("decisions").insert(fallback_record).execute()
        return fallback_record
    except Exception as fallback_error:
        raise RuntimeError(
            f"log_decision fully failed for ticket {ticket_id}, node {node_name}: "
            f"primary={primary_error_msg}, fallback={fallback_error!r}"
        ) from fallback_error
 
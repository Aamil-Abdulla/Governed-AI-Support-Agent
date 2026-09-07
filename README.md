# AI Governance Ticket Pipeline

A LangGraph-style node pipeline for classifying and handling support tickets with
built-in audit logging and human-review routing for high-risk decisions.

## Status

🚧 In progress. Confirmed/built so far:

- [x] `schemas.py` — core Pydantic models
- [x] `state.py` — shared `AgentState` shape
- [x] `audit.py` — fail-safe decision logging
- [x] `db.py` — Supabase client setup
- [x] `intake.py` — partially seen (`_log_and_fallback` helper only; full node logic TBD)
- [ ] `classify.py` — in progress
- [ ] `retrieve.py`
- [ ] `validate_grounding`
- [ ] `decide`
- [ ] `risk_check`
- [ ] `execute_or_queue`

## Architecture

Pipeline nodes operate on a shared `AgentState` (TypedDict), each returning a
partial state update that gets merged in. Node names are constrained by the
`NodeName` literal in `schemas.py`:

```
intake → classify → retrieve → validate_grounding → decide → risk_check → execute_or_queue
```

## Files

### `schemas.py`
Core data models:
- `OrderRecord` — order data shape (id, customer, product, amount, dates, refund eligibility)
- `GroundingResult` — output of grounding/validation checks, with typed failure reasons
  (`stale_data`, `order_not_found`, `field_mismatch`)
- `ClassificationReport` — `ticket_type` (5-way literal: `refund_request`,
  `order_status`, `product_question`, `complaint`, `other`) + `confidence` (float)
- `NodeName` — literal type constraining valid pipeline node names
- `Route` — `auto_execute` | `require_approval`

### `state.py`
`AgentState` TypedDict — the shared state object threaded through all nodes.
Fields are progressively filled in as the ticket moves through the pipeline
(`NotRequired` for anything not yet known), except `decision_log` which
accumulates via `operator.add`.

**Open issue:** no field currently holds the raw ticket message text. Needs
to be added (e.g. `ticket_text: NotRequired[str]`) and set by `intake.py`
before `classify.py` can read it.

### `audit.py`
`log_decision(...)` — the single audit-logging entry point used by every node.
Fail-safe (not fail-open) design:
1. Try full insert into `decisions` table.
2. On failure, try a minimal insert tagged `{node_name}__LOGGING_FAILED` with
   the error as `raw_trace`.
3. On failure again, raise — so the calling node's own try/except can catch
   it and fall back with `risk_level="high"`, `risk_reason="audit_logging_failure"`.

### `db.py`
Supabase client (`SupaBase`), initialized from `SUPABASE_URL` / `SUPABASE_KEY`
env vars via `.env`.

### `intake.py`
Only `_log_and_fallback(...)` confirmed so far — a shared helper for intake's
"expected" failure paths (query failure, ticket not found). Swallows secondary
logging failures to avoid audit-of-audit recursion. Always returns
`risk_level="high"` and a consistent minimal shape. Full node logic (the
happy path, what sets `ticket_id`/order lookup/etc.) not yet reviewed.

## Design patterns established

- **Fail-safe, not fail-open**: any node that can't complete its job routes
  to human review (`risk_level="high"`) rather than silently proceeding.
- **Per-node fallback helpers**: each node gets its own `_log_and_fallback`-
  style helper rather than sharing one across nodes, since failure modes
  differ per node (clean binary failures vs. retryable LLM/API failures).
- **Audit logging wrapped in its own try/except at the call site**: a logging
  failure must never crash the node that's calling it.
- **Prompt injection defense** (for LLM-calling nodes): wrap untrusted text
  in `<<<TICKET_MESSAGE>>> ... <<<END>>>` delimiters and instruct the model
  to treat that span as data, never instructions.

## Environment

Requires a `.env` with:
```
SUPABASE_URL=
SUPABASE_KEY=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
```

## Deployment (Azure OpenAI / Foundry)

- Deployment name: `ticket-classifier`
- Model: `gpt-5-mini` (version `2025-08-07`)
- SKU: `GlobalStandard`, capacity 10
- Resource: `aamilabdulla0-1117-resource` (`westus3`)
- Used by: `classify.py`
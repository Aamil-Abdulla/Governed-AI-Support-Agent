import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_URL = os.environ.get("API_URL", "http://localhost:8000")
API_KEY = os.environ.get("API_KEY", "")
HEADERS = {"X-API-Key": API_KEY}

st.set_page_config(page_title="Governed AI Support Agent", layout="wide")
st.title("Governed AI Support Agent")

if not API_KEY:
    st.error("API_KEY is not set. Add it to your .env file.")
    st.stop()


def api_get(path: str):
    r = requests.get(f"{API_URL}{path}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def api_post(path: str, json=None):
    return requests.post(f"{API_URL}{path}", headers=HEADERS, json=json, timeout=120)


def risk_badge(level: str | None) -> str:
    return {"low": "🟢 low", "medium": "🟡 medium", "high": "🔴 high"}.get(level or "", "⚪ unknown")


def show_decision_log(items: list[dict]):
    for i, d in enumerate(items, 1):
        with st.expander(f"{i}. {d.get('node_name')}  —  {d.get('output_summary') or ''}"):
            st.write(f"**Risk:** {risk_badge(d.get('risk_level'))}  {d.get('risk_reason') or ''}")
            st.write(d.get("plain_language_rationale") or "")
            if d.get("raw_trace"):
                st.code(d["raw_trace"])


tab_process, tab_queue, tab_audit = st.tabs(["Process a ticket", "Approval queue", "Audit trail"])

# ---------- Tab 1: process ----------
with tab_process:
    ticket_id = st.text_input("Ticket ID", key="process_ticket_id")
    if st.button("Run pipeline", disabled=not ticket_id):
        with st.spinner("Running..."):
            try:
                r = api_post(f"/tickets/{ticket_id.strip()}/process")
            except requests.RequestException as e:
                st.error(f"Could not reach the API: {e}")
                r = None
        if r is not None:
            if r.status_code != 200:
                st.error(f"{r.status_code}: {r.json().get('detail', r.text)}")
            else:
                result = r.json()
                c1, c2, c3 = st.columns(3)
                c1.metric("Proposed action", result.get("proposed_action") or "none")
                c2.metric("Route", result.get("route") or "ended early")
                c3.metric("Risk", risk_badge(result.get("risk_level")))
                if result.get("risk_reason"):
                    st.caption(f"Risk reason: {result['risk_reason']}")
                st.subheader("Decision log")
                show_decision_log(result.get("decision_log", []))

# ---------- Tab 2: approval queue ----------
with tab_queue:
    reviewer = st.text_input("Your name (recorded on every review)", key="reviewer")
    if st.button("Refresh queue"):
        st.rerun()

    try:
        pending = api_get("/pending-actions")["items"]
    except requests.RequestException as e:
        st.error(f"Could not load the queue: {e}")
        pending = []

    if not pending:
        st.info("Nothing waiting for approval.")

    for item in pending:
        with st.container(border=True):
            st.markdown(f"**{item['proposed_action']}**  ·  ticket `{item['ticket_id']}`")
            st.write(item.get("plain_language_summary") or "")
            if item.get("risk_reason"):
                st.caption(f"Risk reason: {item['risk_reason']}")
            if item.get("citations"):
                with st.expander("Evidence"):
                    st.code(item["citations"], language="json")

            b1, b2, _ = st.columns([1, 1, 6])
            for label, endpoint, col in (("Approve", "approve", b1), ("Reject", "reject", b2)):
                if col.button(label, key=f"{endpoint}-{item['id']}", disabled=not reviewer.strip()):
                    r = api_post(f"/pending-actions/{item['id']}/{endpoint}", json={"reviewed_by": reviewer.strip()})
                    if r.status_code == 200:
                        st.success(f"{label}d.")
                        st.rerun()
                    else:
                        st.error(f"{r.status_code}: {r.json().get('detail', r.text)}")
    if pending and not reviewer.strip():
        st.caption("Enter your name above to enable the buttons.")

# ---------- Tab 3: audit trail ----------
with tab_audit:
    audit_id = st.text_input("Ticket ID", key="audit_ticket_id")
    if st.button("Load audit trail", disabled=not audit_id):
        try:
            items = api_get(f"/tickets/{audit_id.strip()}/decisions")["items"]
        except requests.RequestException as e:
            st.error(f"Could not load the audit trail: {e}")
            items = []
        if items:
            st.write(f"{len(items)} recorded decisions")
            show_decision_log(items)
        else:
            st.info("No decisions recorded for that ticket.")
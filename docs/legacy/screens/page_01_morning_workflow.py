"""
Page 1 — Morning Workflow (skeleton).
Layout-only: matches UI Blueprint. No backend; placeholder data only.
Run standalone: streamlit run docs/skeleton_pages/page_01_morning_workflow.py
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Placeholder data (replace with real data in real app)
# ---------------------------------------------------------------------------
def _placeholder_has_active_property() -> bool:
    return True  # Set False to see "no property" state


def _placeholder_import_timestamps():
    """Return dict like {"MOVE_OUTS": "2025-03-13T09:00:00", ...} or {}."""
    return {
        "MOVE_OUTS": "2025-03-13T09:00:00",
        "PENDING_MOVE_INS": "2025-03-13T09:00:00",
        "AVAILABLE_UNITS": None,  # missing → warning
        "PENDING_FAS": "2025-03-12",
    }


def _placeholder_missing_move_out_rows():
    """List of dicts with keys: unit_code, move_in_date, report_type."""
    return [
        {"unit_code": "5-1-101", "move_in_date": "2025-03-10", "report_type": "PENDING_MOVE_INS"},
        {"unit_code": "7-2-205", "move_in_date": "2025-03-11", "report_type": "PENDING_MOVE_INS"},
    ]  # Empty list → success message


def _placeholder_risk_metrics():
    return {"vacant_over_7": 2, "sla_breach": 1, "move_in_soon": 3}


def _placeholder_todays_critical():
    """List of dicts: Unit, Event, Date, turnover_id (for nav)."""
    return [
        {"Unit": "5-1-101", "Event": "Move-Out", "Date": "Today", "turnover_id": 1},
        {"Unit": "7-2-205", "Event": "Move-In", "Date": "Today", "turnover_id": 2},
    ]  # Empty → info message


# ---------------------------------------------------------------------------
# Render (structure only)
# ---------------------------------------------------------------------------
def render() -> None:
    st.title("Morning Workflow")
    st.caption("What do I need to fix right now before the day starts?")

    # Active property banner (placeholder)
    if _placeholder_has_active_property():
        st.caption("Active Property: **Sample Property**")
    else:
        st.info("Create a property in the Admin tab to begin.")
        return

    today = date.today()

    # ---------- Section 1: Import Status ----------
    st.subheader("1. Import Status")
    st.caption("Confirm reports are fresh before starting the day.")
    timestamps = _placeholder_import_timestamps()
    labels = {"MOVE_OUTS": "Move-Out", "PENDING_MOVE_INS": "Move-In", "AVAILABLE_UNITS": "Available", "PENDING_FAS": "FAS"}
    if not timestamps:
        st.info("No imports recorded yet. Run imports from Admin or your import process.")
    else:
        for key, label in labels.items():
            ts = timestamps.get(key)
            if not ts:
                st.warning(f"⚠ {label} report not imported today")
            else:
                st.text(f"{label:20} {str(ts)[:16]}")

    st.markdown("---")

    # ---------- Section 2: Units missing move-out date ----------
    st.subheader("2. Units missing move-out date")
    st.caption("Repair queue: add move-out date and create turnover so the unit appears on the board.")
    rows = _placeholder_missing_move_out_rows()
    if not rows:
        st.success("No units in the repair queue.")
    else:
        df = pd.DataFrame([
            {"Unit": r.get("unit_code"), "Move-In Date": r.get("move_in_date") or "—", "Report": r.get("report_type") or "—"}
            for r in rows
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown("**Resolve: create turnover with move-out date**")
        options = [f"{r.get('unit_code')} (conflict)" for r in rows]
        st.selectbox("Select unit to resolve", options=options, key="sk_morning_unit")
        st.date_input("Move-out date", value=today, key="sk_morning_move_out")
        st.button("Create turnover", key="sk_morning_create_turnover")

    st.markdown("---")

    # ---------- Section 3: Turnover risk summary ----------
    st.subheader("3. Turnover risk summary")
    st.caption("Quick counts; open the board or Flag Bridge to act.")
    m = _placeholder_risk_metrics()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Units vacant > 7 days", m["vacant_over_7"])
    with col2:
        st.metric("Units with SLA breach", m["sla_breach"])
    with col3:
        st.metric("Move-ins within 3 days", m["move_in_soon"])
    if m["sla_breach"] > 0:
        st.button("Open Flag Bridge (SLA breach filter)", key="sk_morning_flag_bridge")
    st.button("Open DMRB Board", key="sk_morning_board")

    st.markdown("---")

    # ---------- Section 4: Today's critical units ----------
    st.subheader("4. Today's critical units")
    st.caption("Move-ins, move-outs, and ready dates today. Click a row to open Turnover Detail.")
    critical = _placeholder_todays_critical()
    if not critical:
        st.info("No move-ins, move-outs, or ready dates today.")
    else:
        df_c = pd.DataFrame([{"Unit": x["Unit"], "Event": x["Event"], "Date": x["Date"]} for x in critical])
        st.dataframe(df_c, use_container_width=True, hide_index=True)
        st.caption("Open a unit in Turnover Detail:")
        options = [f"{x['Unit']} — {x['Event']}" for x in critical]
        st.selectbox("Select unit", options=options, key="sk_morning_critical_unit")
        st.button("Open Turnover Detail", key="sk_morning_open_detail")


if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Morning Workflow (skeleton)")
    render()

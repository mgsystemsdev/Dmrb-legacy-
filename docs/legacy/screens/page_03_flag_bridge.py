"""
Page 3 — Flag Bridge (skeleton).
Layout-only: filter row (6 dropdowns), metrics row (3), read-only breach table.
Placeholder data only. Run standalone: streamlit run docs/skeleton_pages/page_03_flag_bridge.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Placeholder options and data
# ---------------------------------------------------------------------------
STATUS_OPTIONS = ["Vacant not ready", "Notice", "Notice + SMI", "Vacant", "SMI", "Move-In", "Available"]
NVM_OPTS = ["All", "Notice", "Notice + SMI", "Vacant", "SMI", "Move-In"]
BRIDGE_OPTS = ["All", "Insp Breach", "SLA Breach", "SLA MI Breach", "Plan Breach"]
VALUE_OPTS = ["All", "Yes", "No"]


def _placeholder_has_active_property() -> bool:
    return True


def _placeholder_rows():
    """List of breach row dicts. Empty → no rows state."""
    return [
        {
            "turnover_id": 1,
            "unit_code": "5-1-101",
            "status": "Vacant not ready",
            "dv": 12,
            "move_in_date": "03/20/2025",
            "alert": "⚠",
            "has_violation": True,
            "inspection_sla_breach": True,
            "sla_breach": True,
            "sla_movein_breach": False,
            "plan_breach": False,
        },
        {
            "turnover_id": 2,
            "unit_code": "7-2-205",
            "status": "Notice",
            "dv": 8,
            "move_in_date": "03/22/2025",
            "alert": "",
            "has_violation": False,
            "inspection_sla_breach": False,
            "sla_breach": False,
            "sla_movein_breach": True,
            "plan_breach": True,
        },
    ]


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def render() -> None:
    if not _placeholder_has_active_property():
        st.info("Create a property in the Admin tab to begin.")
        return
    st.caption("Active Property: **Sample Property**")

    rows = _placeholder_rows()
    n_viol = sum(1 for r in rows if r.get("has_violation"))
    n_breach = sum(
        1
        for r in rows
        if r.get("inspection_sla_breach")
        or r.get("sla_breach")
        or r.get("sla_movein_breach")
        or r.get("plan_breach")
    )

    # ---------- Filter row (bordered), 6 equal columns ----------
    with st.container(border=True):
        c0, c1, c2, c3, c4, c5 = st.columns(6)
        with c0:
            st.selectbox("Phase", ["All", "5", "7", "8"], index=0, key="sk_fb_phase")
        with c1:
            st.selectbox("Status", ["All"] + STATUS_OPTIONS, index=0, key="sk_fb_status")
        with c2:
            st.selectbox("N/V/M", NVM_OPTS, index=0, key="sk_fb_nvm")
        with c3:
            st.selectbox("Assign", ["All", "Alice", "Bob"], index=0, key="sk_fb_assign")
        with c4:
            st.selectbox("Flag Bridge", BRIDGE_OPTS, index=0, key="sk_fb_bridge")
        with c5:
            st.selectbox("Value", VALUE_OPTS, index=0, key="sk_fb_value")

    # ---------- Metrics row (bordered), 3 columns ----------
    with st.container(border=True):
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Units", len(rows))
        m2.metric("Violations", n_viol)
        m3.metric("Units w/ Breach", n_breach)

    if not rows:
        st.info("No rows match filters.")
        return

    # ---------- Breach table (read-only; checkbox for nav to detail) ----------
    tid_map = []
    bridge_data = []
    for r in rows:
        tid_map.append(r.get("turnover_id"))
        bridge_data.append({
            "▶": False,
            "Unit": r.get("unit_code", ""),
            "Status": r.get("status", ""),
            "DV": r.get("dv"),
            "Move-In": r.get("move_in_date", ""),
            "Alert": r.get("alert", ""),
            "Viol": "🔴" if r.get("has_violation") else "—",
            "Insp": "🔴" if r.get("inspection_sla_breach") else "—",
            "SLA": "🔴" if r.get("sla_breach") else "—",
            "MI": "🔴" if r.get("sla_movein_breach") else "—",
            "Plan": "🔴" if r.get("plan_breach") else "—",
        })

    bridge_df = pd.DataFrame(bridge_data)
    st.data_editor(
        bridge_df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=["Unit", "Status", "DV", "Move-In", "Alert", "Viol", "Insp", "SLA", "MI", "Plan"],
        column_config={
            "▶": st.column_config.CheckboxColumn("▶", width=40),
            "Unit": st.column_config.TextColumn("Unit"),
            "Status": st.column_config.TextColumn("Status"),
            "DV": st.column_config.NumberColumn("DV", width=50),
            "Move-In": st.column_config.TextColumn("Move-In"),
            "Alert": st.column_config.TextColumn("Alert"),
            "Viol": st.column_config.TextColumn("Viol", width=50),
            "Insp": st.column_config.TextColumn("Insp", width=50),
            "SLA": st.column_config.TextColumn("SLA", width=50),
            "MI": st.column_config.TextColumn("MI", width=50),
            "Plan": st.column_config.TextColumn("Plan", width=50),
        },
        column_order=["▶", "Unit", "Status", "DV", "Move-In", "Alert", "Viol", "Insp", "SLA", "MI", "Plan"],
        key="sk_fb_editor",
    )


if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Flag Bridge (skeleton)")
    render()

"""
Page 2 — DMRB Board (skeleton).
Layout-only: filter bar, metrics bar, Unit Info / Unit Tasks tabs. Placeholder data only.
Run standalone: streamlit run docs/skeleton_pages/page_02_dmrb_board.py
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Placeholder options (replace with ui.state / backend in real app)
# ---------------------------------------------------------------------------
STATUS_OPTIONS = ["Vacant not ready", "Notice", "Notice + SMI", "Vacant", "SMI", "Move-In", "Available"]
NVM_OPTS = ["All", "Notice", "Notice + SMI", "Vacant", "SMI", "Move-In"]
CONFIRM_LABELS = ["Pending", "Confirmed"]
EXEC_LABELS = ["Not Started", "In Progress", "Vendor Completed", "Skipped"]
TASK_COLS = [
    "Inspection", "Carpet Bid", "Make Ready Bid", "Paint",
    "Make Ready", "Housekeeping", "Carpet Clean", "Final Walk",
]


def _placeholder_has_active_property() -> bool:
    return True


def _placeholder_rows():
    """List of turnover-like dicts. Empty list → no rows state."""
    return [
        {
            "turnover_id": 1,
            "unit_code": "5-1-101",
            "status": "Vacant not ready",
            "move_out_date": date(2025, 3, 1),
            "ready_date": date(2025, 3, 15),
            "dv": 12,
            "move_in_date": date(2025, 3, 20),
            "dtbr": 7,
            "nvm": "Vacant",
            "wd_summary": "—",
            "qc": "Pending",
            "alert": "",
            "notes": "Sample note",
            "legal": True,
            "task_exec": {tc: "In Progress" for tc in TASK_COLS},
            "task_dates": {tc: date(2025, 3, 5) for tc in TASK_COLS},
        },
        {
            "turnover_id": 2,
            "unit_code": "7-2-205",
            "status": "Notice",
            "move_out_date": date(2025, 3, 5),
            "ready_date": date(2025, 3, 18),
            "dv": 8,
            "move_in_date": date(2025, 3, 22),
            "dtbr": 4,
            "nvm": "Notice",
            "wd_summary": "Yes",
            "qc": "Confirmed",
            "alert": "⚠",
            "notes": "",
            "legal": False,
            "task_exec": {tc: "Not Started" for tc in TASK_COLS},
            "task_dates": {tc: date(2025, 3, 10) for tc in TASK_COLS},
        },
    ]


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def render() -> None:
    # Active property banner
    if not _placeholder_has_active_property():
        st.info("Create a property in the Admin tab to begin.")
        return
    st.caption("Active Property: **Sample Property**")

    rows = _placeholder_rows()
    n_active = len(rows)
    n_crit = sum(1 for r in rows if r.get("alert"))  # placeholder crit

    # ---------- Filter bar (bordered) ----------
    with st.container(border=True):
        c0, c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 1, 1, 1, 1, 1, 1, 1])
        with c0:
            st.text_input("Search unit", value="", key="sk_board_search")
        with c1:
            st.selectbox("Phase", ["All", "5", "7", "8"], index=0, key="sk_board_phase")
        with c2:
            st.selectbox("Status", ["All"] + STATUS_OPTIONS, index=0, key="sk_board_status")
        with c3:
            st.selectbox("N/V/M", NVM_OPTS, index=0, key="sk_board_nvm")
        with c4:
            st.selectbox("Assign", ["All", "Alice", "Bob"], index=0, key="sk_board_assign")
        with c5:
            st.selectbox("QC", ["All", "QC Done", "QC Not done"], index=0, key="sk_board_qc")
        with c6:
            st.metric("Active", n_active)
        with c7:
            st.metric("CRIT", n_crit)

    # ---------- Metrics bar (bordered) ----------
    with st.container(border=True):
        n_viol = sum(1 for r in rows if r.get("alert"))
        n_plan = 0
        n_sla = 0
        n_mi_risk = 0
        n_stalled = 0
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Active Units", n_active)
        m2.metric("Violations", n_viol)
        m3.metric("Plan Breach", n_plan)
        m4.metric("SLA Breach", n_sla)
        m5.metric("Move-In Risk", n_mi_risk)
        m6.metric("Work Stalled", n_stalled)

    if not rows:
        st.info("No turnovers match filters.")
        return

    # ---------- Build Unit Info and Unit Tasks data ----------
    info_data = []
    task_data = []
    tid_map = []

    for r in rows:
        tid_map.append(r["turnover_id"])
        info_data.append({
            "▶": False,
            "Unit": r["unit_code"],
            "Status": r["status"],
            "Move-Out": r["move_out_date"],
            "Ready Date": r["ready_date"],
            "DV": r["dv"],
            "Move-In": r["move_in_date"],
            "DTBR": r["dtbr"],
            "N/V/M": r["nvm"],
            "W/D": r["wd_summary"],
            "Quality Control": r["qc"],
            "Alert": r["alert"],
            "Notes": r["notes"],
        })
        legal_dot = "🟢" if r.get("legal") else "🔴"
        task_row = {
            "▶": False,
            "Unit": r["unit_code"],
            "⚖": legal_dot,
            "Status": r["status"],
            "DV": r["dv"],
            "DTBR": r["dtbr"],
        }
        for tc in TASK_COLS:
            task_row[tc] = r["task_exec"].get(tc, "Not Started")
            task_row[f"{tc} Date"] = r["task_dates"].get(tc)
        task_data.append(task_row)

    df_info = pd.DataFrame(info_data)
    df_task = pd.DataFrame(task_data)
    task_date_cols = [f"{tc} Date" for tc in TASK_COLS]

    # ---------- Tabs: Unit Info / Unit Tasks ----------
    tab_info, tab_tasks = st.tabs(["Unit Info", "Unit Tasks"])

    with tab_info:
        info_col_config = {
            "▶": st.column_config.CheckboxColumn("▶", width=40),
            "Unit": st.column_config.TextColumn("Unit"),
            "Status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS),
            "Move-Out": st.column_config.DateColumn("Move-Out", format="MM/DD/YYYY"),
            "Ready Date": st.column_config.DateColumn("Ready Date", format="MM/DD/YYYY"),
            "DV": st.column_config.NumberColumn("DV", width=50),
            "Move-In": st.column_config.DateColumn("Move-In", format="MM/DD/YYYY"),
            "DTBR": st.column_config.NumberColumn("DTBR", width=60),
            "N/V/M": st.column_config.TextColumn("N/V/M", width=80),
            "W/D": st.column_config.TextColumn("W/D", width=50),
            "Quality Control": st.column_config.SelectboxColumn("Quality Control", options=CONFIRM_LABELS),
            "Alert": st.column_config.TextColumn("Alert"),
            "Notes": st.column_config.TextColumn("Notes", width=120),
        }
        st.data_editor(
            df_info,
            column_config=info_col_config,
            hide_index=True,
            num_rows="fixed",
            use_container_width=True,
            key="sk_board_info_editor",
            disabled=["Unit", "DV", "DTBR", "N/V/M", "W/D", "Alert", "Notes"],
        )

    with tab_tasks:
        task_col_config = {
            "▶": st.column_config.CheckboxColumn("▶", width=40),
            "Unit": st.column_config.TextColumn("Unit"),
            "⚖": st.column_config.TextColumn("⚖", width=35),
            "Status": st.column_config.TextColumn("Status"),
            "DV": st.column_config.NumberColumn("DV", width=50),
            "DTBR": st.column_config.NumberColumn("DTBR", width=60),
            **{tc: st.column_config.SelectboxColumn(tc, options=EXEC_LABELS) for tc in TASK_COLS},
            **{dc: st.column_config.DateColumn(dc, format="MM/DD/YYYY") for dc in task_date_cols},
        }
        task_col_order = ["▶", "Unit", "⚖", "Status", "DV", "DTBR"]
        for tc, dc in zip(TASK_COLS, task_date_cols):
            task_col_order.extend([tc, dc])
        st.data_editor(
            df_task,
            column_config=task_col_config,
            column_order=task_col_order,
            hide_index=True,
            num_rows="fixed",
            use_container_width=True,
            key="sk_board_task_editor",
            disabled=["Unit", "⚖", "Status", "DV", "DTBR"],
        )


if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="DMRB Board (skeleton)")
    render()

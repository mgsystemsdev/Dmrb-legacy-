import streamlit as st
import pandas as pd

from ui.logic.filters import (
    filter_by_phase,
    filter_by_status,
    filter_by_nvm,
)
from ui.logic.filter_controls import render_filter_controls


TASK_STATUS_COLUMNS = [
    ("Insp", "Insp_status"),
    ("Paint", "Paint_status"),
    ("MR", "MR_Status"),
    ("HK", "HK_Status"),
    ("CC", "CC_status"),
]

STALL_DISPLAY_COLUMNS = [
    "Unit",
    "Status",
    "DV",
    "Operational_State",
    "Table_Current_Task",
    "Table_Next_Task",
    "Aging_Business_Days",
    "Attention_Badge",
]


def render(df: pd.DataFrame):

    st.title("Pivot Analytics")
    st.caption("Operational pivot tables for turnover performance analysis.")

    # -------------------------------------------------
    # Shared Filter Controls
    # -------------------------------------------------

    selected_phase, selected_status, selected_nvm = render_filter_controls(
        df, key_prefix="pa"
    )

    # -------------------------------------------------
    # Apply Filters
    # -------------------------------------------------

    filtered = df.copy()
    filtered = filter_by_phase(filtered, selected_phase)
    filtered = filter_by_status(filtered, selected_status)
    filtered = filter_by_nvm(filtered, selected_nvm)

    if filtered.empty:
        st.info("No units match the current filters.")
        return

    # =====================================================
    # Expander 1 – Task Pipeline
    # =====================================================

    with st.expander("Task Pipeline", expanded=True):
        st.caption("Task completion counts across the pipeline.")

        rows = []
        for task_label, col in TASK_STATUS_COLUMNS:
            if col not in filtered.columns:
                continue
            counts = filtered[col].fillna("Unknown").value_counts()
            row = counts.to_dict()
            row["Task"] = task_label
            rows.append(row)

        if rows:
            pipeline = pd.DataFrame(rows).set_index("Task").fillna(0).astype(int)
            st.dataframe(pipeline, use_container_width=True)
        else:
            st.info("No task-status columns found in the data.")

    # =====================================================
    # Expander 2 – Aging Dashboard
    # =====================================================

    with st.expander("Aging Dashboard", expanded=False):
        if "Operational_State" not in filtered.columns or "DV" not in filtered.columns:
            st.info("Required columns (Operational_State, DV) not found.")
        else:
            dv = pd.to_numeric(filtered["DV"], errors="coerce")
            aging = (
                dv.groupby(filtered["Operational_State"])
                .agg(["count", "mean", "max"])
                .round(0)
                .fillna(0)
                .astype(int)
            )
            aging.columns = ["Units", "Avg Days", "Max Days"]
            st.dataframe(aging, use_container_width=True)

            if "P" in filtered.columns:
                st.markdown("**Average Days Vacant by Operational State × Phase**")
                cross = (
                    dv.groupby([filtered["Operational_State"], filtered["P"]])
                    .mean()
                    .round(0)
                    .unstack(fill_value=0)
                    .fillna(0)
                    .astype(int)
                )
                st.dataframe(cross, use_container_width=True)

    # =====================================================
    # Expander 3 – Workload
    # =====================================================

    with st.expander("Workload", expanded=False):
        st.caption("Unit distribution by assignment and task state.")

        if "Assign" not in filtered.columns:
            st.info("Column 'Assign' not found.")
        else:
            if "Task_State" in filtered.columns:
                wl1 = pd.crosstab(
                    filtered["Assign"], filtered["Task_State"], margins=True
                )
                st.dataframe(wl1, use_container_width=True)
            else:
                st.info("Column 'Task_State' not found.")

            if "Status_Norm" in filtered.columns:
                wl2 = pd.crosstab(
                    filtered["Assign"], filtered["Status_Norm"], margins=True
                )
                st.dataframe(wl2, use_container_width=True)

    # =====================================================
    # Expander 4 – Stall Tracker
    # =====================================================

    with st.expander("Stall Tracker", expanded=False):
        if "Is_Task_Stalled" not in filtered.columns:
            st.info("Column 'Is_Task_Stalled' not found.")
        else:
            stalled = filtered[
                (filtered["Is_Task_Stalled"] == True)
                | (filtered["Is_Task_Stalled"].astype(str).str.strip() == "True")
            ]

            if stalled.empty:
                st.info("No stalled units.")
            else:
                st.metric("Stalled Units", len(stalled))
                display_cols = [
                    c for c in STALL_DISPLAY_COLUMNS if c in stalled.columns
                ]
                st.dataframe(
                    stalled[display_cols].reset_index(drop=True),
                    use_container_width=True,
                )

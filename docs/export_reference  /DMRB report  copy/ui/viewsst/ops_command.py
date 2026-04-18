import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

import streamlit as st
import pandas as pd
import numpy as np

from facts import run_facts
from intelligence import run_intelligence
from sla import run_sla


@st.cache_data
def enrich(df):
    df = run_facts(df)
    df = run_intelligence(df)
    df = run_sla(df)
    return df


def _safe_cols(df, cols):
    return [c for c in cols if c in df.columns]


def render(df):

    st.title("Ops Command Center")

    # --------------------------------------------------
    # Pipeline enrichment
    # --------------------------------------------------
    df = enrich(df)

    df = df.replace("#NUM!", np.nan)
    if "Days_To_MoveIn" in df.columns:
        df["Days_To_MoveIn"] = pd.to_numeric(df["Days_To_MoveIn"], errors="coerce")

    df["Risk_Flag"] = (
        (df["Days_To_MoveIn"] <= 10) &
        (df["Task_Completion_Ratio"] < 80)
    )

    # --------------------------------------------------
    # Sidebar filters
    # --------------------------------------------------
    with st.sidebar:
        st.subheader("Ops Filters")

        phases = sorted(df["P"].dropna().unique().tolist())
        sel_phase = st.multiselect("Phase (P)", phases, default=[], key="ops_phase")

        buildings = sorted(df["B"].dropna().unique().tolist())
        sel_building = st.multiselect("Building (B)", buildings, default=[], key="ops_building")

        assigns = sorted(df["Assign"].dropna().unique().tolist())
        sel_assign = st.multiselect("Assign", assigns, default=[], key="ops_assign")

        statuses = sorted(df["Status_Norm"].dropna().unique().tolist())
        sel_status = st.multiselect("Status", statuses, default=[], key="ops_status")

        high_risk_only = st.checkbox("Show only high risk", value=False, key="ops_high_risk")

    if sel_phase:
        df = df[df["P"].isin(sel_phase)]
    if sel_building:
        df = df[df["B"].isin(sel_building)]
    if sel_assign:
        df = df[df["Assign"].isin(sel_assign)]
    if sel_status:
        df = df[df["Status_Norm"].isin(sel_status)]
    if high_risk_only:
        df = df[df["Risk_Flag"] == True]

    # --------------------------------------------------
    # KPI row
    # --------------------------------------------------
    vacant = df[df["Is_Vacant"] == True] if "Is_Vacant" in df.columns else df.iloc[0:0]
    smi = df[df["Is_SMI"] == True] if "Is_SMI" in df.columns else df.iloc[0:0]

    k1, k2, k3, k4, k5 = st.columns(5)

    k1.metric("Total Vacant Units", len(vacant))
    k2.metric("Total SMI Units", len(smi))

    if "Days_To_MoveIn" in df.columns:
        urgent = df[(df["Days_To_MoveIn"] < 10) & (df["Days_To_MoveIn"] >= 0)]
        k3.metric("Units < 10 Days to Move-In", len(urgent))
    else:
        k3.metric("Units < 10 Days to Move-In", 0)

    if "Is_Task_Stalled" in df.columns and len(vacant) > 0:
        stalled_pct = round(vacant["Is_Task_Stalled"].sum() / len(vacant) * 100, 1)
        k4.metric("% Stalled Units", f"{stalled_pct}%")
    else:
        k4.metric("% Stalled Units", "0%")

    if "Aging_Business_Days" in df.columns and len(vacant) > 0:
        avg_aging = round(vacant["Aging_Business_Days"].mean(), 1)
        k5.metric("Avg Aging Days", avg_aging)
    else:
        k5.metric("Avg Aging Days", 0)

    st.divider()

    # --------------------------------------------------
    # High Risk Move-In Panel
    # --------------------------------------------------
    st.subheader("🔥 Immediate Move-In Risk")

    risk_mask = pd.Series(True, index=df.index)
    if "Is_SMI" in df.columns:
        risk_mask &= df["Is_SMI"] == True
    if "Days_To_MoveIn" in df.columns:
        risk_mask &= df["Days_To_MoveIn"] <= 10
    if "Task_Completion_Ratio" in df.columns:
        risk_mask &= df["Task_Completion_Ratio"] < 80

    risk_df = df[risk_mask].sort_values("Days_To_MoveIn", ascending=True)

    if len(risk_df) > 0:
        st.markdown(f"**{len(risk_df)} units at immediate risk**")
        risk_cols = _safe_cols(risk_df, [
            "Unit", "Status", "Days_To_MoveIn", "Task_Completion_Ratio",
            "Table_Current_Task", "Attention_Badge", "Assign", "Notes",
        ])
        st.dataframe(risk_df[risk_cols], use_container_width=True)
    else:
        st.success("No immediate move-in risks.")

    st.divider()

    # --------------------------------------------------
    # Stalled Units Panel
    # --------------------------------------------------
    st.subheader("⏸ Stalled Units")

    stall_mask = pd.Series(False, index=df.index)
    if "Is_Task_Stalled" in df.columns:
        stall_mask |= df["Is_Task_Stalled"] == True
    if "Operational_State" in df.columns:
        stall_mask |= df["Operational_State"] == "Work Stalled"

    stalled = df[stall_mask]

    if len(stalled) > 0:
        if "Table_Current_Task" in stalled.columns:
            summary = stalled.groupby("Table_Current_Task").size().reset_index(name="Count")
            st.dataframe(summary, use_container_width=True)

        stall_cols = _safe_cols(stalled, [
            "Unit", "Status", "DV", "Operational_State", "Table_Current_Task",
            "Table_Next_Task", "Aging_Business_Days", "Assign", "Attention_Badge",
        ])
        st.dataframe(stalled[stall_cols], use_container_width=True)
    else:
        st.success("No stalled units.")

    st.divider()

    # --------------------------------------------------
    # Aging Watchlist
    # --------------------------------------------------
    st.subheader("📈 Aging Watchlist")

    aging_df = vacant.copy()
    if "Aging_Business_Days" in aging_df.columns and "P" in aging_df.columns:
        aging_df["Above_Phase_Avg"] = aging_df["Aging_Business_Days"] > aging_df.groupby("P")["Aging_Business_Days"].transform("mean")
    else:
        aging_df["Above_Phase_Avg"] = False

    aging_df = aging_df.sort_values("Aging_Business_Days", ascending=False).head(30)

    aging_cols = _safe_cols(aging_df, [
        "Unit", "Status", "P", "B", "Aging_Business_Days",
        "Above_Phase_Avg", "Operational_State", "Attention_Badge",
    ])
    st.dataframe(aging_df[aging_cols], use_container_width=True)

    st.divider()

    # --------------------------------------------------
    # HOLD / PARTS Risk
    # --------------------------------------------------
    st.subheader("🚧 Hold / Notes Risk")

    if "Note_Category" in df.columns:
        hold_df = df[df["Note_Category"].isin(["HOLD", "ISSUE", "REOPEN"])]
        hold_df = hold_df.sort_values("Aging_Business_Days", ascending=False)

        if len(hold_df) > 0:
            hold_cols = _safe_cols(hold_df, [
                "Unit", "Status", "Note_Category", "Note_Text",
                "Aging_Business_Days", "Days_To_MoveIn", "Assign",
            ])
            st.dataframe(hold_df[hold_cols], use_container_width=True)
        else:
            st.info("No HOLD / ISSUE / REOPEN notes found.")
    else:
        st.info("Note_Category column not available.")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

import streamlit as st
import pandas as pd
import numpy as np

from facts import run_facts
from intelligence import run_intelligence
from sla import run_sla

DISPLAY_COLS = [
    "Phase", "B", "Unit", "Risk_Flag", "Risk_Score",
    "Days_To_MoveIn", "Task_Completion_Ratio", "Table_Current_Task",
    "Assign", "Operational_State",
]

COL_RENAME = {
    "B": "Building",
    "Days_To_MoveIn": "Days to Move-In",
    "Task_Completion_Ratio": "Completion %",
    "Table_Current_Task": "Current Task",
    "Operational_State": "Ops State",
}


@st.cache_data
def enrich(df):
    df = run_facts(df)
    df = run_intelligence(df)
    df = run_sla(df)
    return df


def _safe_cols(df, cols):
    return [c for c in cols if c in df.columns]


def _score(df):
    df["Risk_Score"] = 0

    if "Days_To_MoveIn" in df.columns:
        df.loc[df["Days_To_MoveIn"] <= 7, "Risk_Score"] += 30
    if "Task_Completion_Ratio" in df.columns:
        df.loc[df["Task_Completion_Ratio"] < 60, "Risk_Score"] += 25
    if "Is_Task_Stalled" in df.columns:
        df.loc[df["Is_Task_Stalled"] == True, "Risk_Score"] += 20
    if "Note_Category" in df.columns:
        df.loc[df["Note_Category"].isin(["HOLD", "PARTS"]), "Risk_Score"] += 15
    if "Aging_Business_Days" in df.columns:
        avg = df["Aging_Business_Days"].mean()
        if pd.notna(avg):
            df.loc[df["Aging_Business_Days"] > avg, "Risk_Score"] += 10
    if "Assign" in df.columns:
        df.loc[df["Assign"].astype(str).str.strip().str.lower() == "total", "Risk_Score"] += 10

    df["Risk_Level"] = pd.cut(
        df["Risk_Score"],
        bins=[-1, 30, 60, 200],
        labels=["Low", "Medium", "High"],
    )

    df["Risk_Flag"] = df["Risk_Level"].map({
        "High": "🔴 High",
        "Medium": "🟡 Medium",
        "Low": "🟢 Low",
    })

    return df


def render(df):

    st.title("🔮 Predict — Risk & Urgency")

    df = enrich(df)
    df = df.replace("#NUM!", np.nan)

    if "Days_To_MoveIn" in df.columns:
        df["Days_To_MoveIn"] = pd.to_numeric(df["Days_To_MoveIn"], errors="coerce")

    if "P" in df.columns:
        df = df.rename(columns={"P": "Phase"})
        df["Phase"] = pd.to_numeric(df["Phase"], errors="coerce")

    df = _score(df)

    ranked = df.sort_values(
        ["Risk_Score", "Days_To_MoveIn"],
        ascending=[False, True],
        na_position="last",
    )

    # --------------------------------------------------
    # Sidebar
    # --------------------------------------------------
    with st.sidebar:
        st.subheader("Predict Filters")
        high_only = st.checkbox("Show Only High Risk", value=False, key="pred_high_only")

    if high_only:
        ranked = ranked[ranked["Risk_Level"] == "High"]

    # --------------------------------------------------
    # KPI row
    # --------------------------------------------------
    high_count = (ranked["Risk_Level"] == "High").sum()
    med_count = (ranked["Risk_Level"] == "Medium").sum()
    low_count = (ranked["Risk_Level"] == "Low").sum()

    k1, k2, k3 = st.columns(3)
    k1.metric("🔴 High Risk", int(high_count))
    k2.metric("🟡 Medium Risk", int(med_count))
    k3.metric("🟢 Low Risk", int(low_count))

    st.divider()

    # --------------------------------------------------
    # High Risk
    # --------------------------------------------------
    high = ranked[ranked["Risk_Level"] == "High"]
    st.subheader("🔴 High Risk Units")

    if len(high) > 0:
        cols = _safe_cols(high, DISPLAY_COLS)
        st.dataframe(
            high[cols].rename(columns=COL_RENAME).reset_index(drop=True),
            use_container_width=True,
        )
    else:
        st.success("No high risk units.")

    st.divider()

    # --------------------------------------------------
    # Medium Risk
    # --------------------------------------------------
    medium = ranked[ranked["Risk_Level"] == "Medium"]
    with st.expander(f"🟡 Medium Risk Units ({len(medium)})", expanded=False):
        if len(medium) > 0:
            cols = _safe_cols(medium, DISPLAY_COLS)
            st.dataframe(
                medium[cols].rename(columns=COL_RENAME).reset_index(drop=True),
                use_container_width=True,
            )
        else:
            st.info("No medium risk units.")

    st.divider()

    # --------------------------------------------------
    # Risk Distribution
    # --------------------------------------------------
    st.subheader("📊 Risk Distribution")
    dist = ranked["Risk_Level"].value_counts().reindex(["High", "Medium", "Low"], fill_value=0)
    st.bar_chart(dist)

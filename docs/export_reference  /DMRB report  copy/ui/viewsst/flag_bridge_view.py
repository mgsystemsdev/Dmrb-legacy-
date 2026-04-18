import streamlit as st
import pandas as pd

from ui.logic.filters import (
    BREACH_MAP,
    filter_by_phase,
    filter_by_status,
    filter_by_nvm,
    filter_by_breach,
    normalize_excel_dates,
)

from ui.logic.filter_controls import render_filter_controls

DISPLAY_COLS = [
    "Unit",
    "Status",
    "DV",
    "Move_in",
    "Attention_Badge",
    "Violation",
    "Inspection_SLA_Breach",
    "SLA_Breach",
    "SLA_MoveIn_Breach",
    "Plan_Breach",
]

COLUMN_CONFIG = {
    "Unit": "Unit",
    "Status": "Status",
    "DV": "Days Vacant",
    "Move_in": "Move-In",
    "Attention_Badge": "Alert",
    "Violation": "Violation",
    "Inspection_SLA_Breach": "Insp Breach",
    "SLA_Breach": "SLA Breach",
    "SLA_MoveIn_Breach": "SLA MI Breach",
    "Plan_Breach": "Plan Bridge",
}


def _bool_to_yes_no(series: pd.Series) -> pd.Series:
    return series.map({True: "Yes", False: "No", "True": "Yes", "False": "No"}).fillna("No")


def render(df):

    st.title("Flag Bridge")

    st.caption(
        "Breach and violation overview. Filter by bridge category "
        "to isolate units with SLA, plan, or inspection breaches."
    )

    col_filters, col_breach, col_yesno = st.columns([3, 1, 0.5])

    with col_filters:
        selected_phase, selected_status, selected_nvm = \
            render_filter_controls(df, key_prefix="fb")

    with col_breach:
        breach_options = [k for k in BREACH_MAP if k != "Any Breach"]
        selected_breach = st.selectbox(
            "Flag Bridge",
            breach_options,
            key="fb_breach",
        )

    with col_yesno:
        if selected_breach == "All":
            st.selectbox("Value", ["—"], key="fb_yesno_disabled", disabled=True)
            breach_value = "All"
        else:
            breach_value = st.selectbox(
                "Value",
                ["All", "Yes", "No"],
                key="fb_yesno",
            )

    filtered = df.copy()
    filtered = filter_by_phase(filtered, selected_phase)
    filtered = filter_by_status(filtered, selected_status)
    filtered = filter_by_nvm(filtered, selected_nvm)

    if selected_breach != "All":
        target_col = BREACH_MAP[selected_breach]
        if breach_value == "Yes":
            filtered = filtered[filtered[target_col] == True]
        elif breach_value == "No":
            filtered = filtered[filtered[target_col] == False]

    filtered = normalize_excel_dates(filtered)

    breach_flags = filtered[["Inspection_SLA_Breach", "SLA_Breach", "SLA_MoveIn_Breach", "Plan_Breach"]]
    filtered["Violation"] = breach_flags.any(axis=1).map({True: "Yes", False: "No"})

    breach_cols = ["Inspection_SLA_Breach", "SLA_Breach", "SLA_MoveIn_Breach", "Plan_Breach"]
    for col in breach_cols:
        if col in filtered.columns:
            filtered[col] = _bool_to_yes_no(filtered[col])

    available = [c for c in DISPLAY_COLS if c in filtered.columns]

    total = len(filtered)
    violations = (filtered["Violation"] == "Yes").sum()
    any_breach = (
        (filtered.get("Inspection_SLA_Breach") == "Yes") |
        (filtered.get("SLA_Breach") == "Yes") |
        (filtered.get("SLA_MoveIn_Breach") == "Yes") |
        (filtered.get("Plan_Breach") == "Yes")
    ).sum()

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Units", total)
    m2.metric("Violations", int(violations))
    m3.metric("Units w/ Breach", int(any_breach))

    st.dataframe(
        filtered[available],
        use_container_width=True,
        height=650,
        column_config=COLUMN_CONFIG,
    )

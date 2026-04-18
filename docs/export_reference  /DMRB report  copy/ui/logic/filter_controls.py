import streamlit as st
from ui.logic.filters import STATUS_GROUPS


def render_filter_controls(df, *, key_prefix):

    col1, col2, col3 = st.columns(3)

    selected_phase = col1.selectbox(
        "Phase",
        ["All"] + sorted(df["P"].dropna().unique().tolist()),
        key=f"{key_prefix}_phase",
    )

    selected_status = col2.selectbox(
        "Status",
        list(STATUS_GROUPS.keys()),
        key=f"{key_prefix}_status",
    )

    selected_nvm = col3.selectbox(
        "N/V/M",
        ["All"] + sorted(df["N/V/M"].dropna().unique().tolist()),
        key=f"{key_prefix}_nvm",
    )

    return selected_phase, selected_status, selected_nvm

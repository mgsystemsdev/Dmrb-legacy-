import streamlit as st
import pandas as pd

from ui.logic.filters import (
    filter_by_phase,
    filter_by_status,
    filter_by_nvm,
    sort_by_movein_then_dv,
)

from ui.logic.filter_controls import render_filter_controls


REQUIRED_COLUMNS = [
    "Unit",
    "Status",
    "DV",
    "Move_in",
    "Attention_Badge",
    "Status_Norm",
    "N/V/M",
    "P",
]


def render(df: pd.DataFrame):

    # -------------------------------------------------
    # Column Safety Check
    # -------------------------------------------------

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        st.error(f"Missing required columns: {missing}")
        return

    st.title("Unit Overview")

    st.caption(
        "Operational unit list. Ordering, inclusion, and priority are "
        "fully determined upstream by the engine."
    )

    # -------------------------------------------------
    # Shared Filter Controls
    # -------------------------------------------------

    selected_phase, selected_status, selected_nvm = \
        render_filter_controls(df, key_prefix="uo")

    # -------------------------------------------------
    # Logic Pipeline (Pure Composition)
    # -------------------------------------------------

    filtered = df.copy()
    filtered = filter_by_phase(filtered, selected_phase)
    filtered = filter_by_status(filtered, selected_status)
    filtered = filter_by_nvm(filtered, selected_nvm)

    filtered = sort_by_movein_then_dv(filtered)

    # Format date for display only
    filtered["Move_in_fmt"] = pd.to_datetime(
        filtered["Move_in"], errors="coerce"
    ).dt.strftime("%m/%d/%Y").fillna("")

    # -------------------------------------------------
    # Output
    # -------------------------------------------------

    st.markdown(f"**{len(filtered)} units**")

    with st.expander("View Units", expanded=True):

        header = st.columns([1.2, 1.5, 1.2, 1.2, 1.5])
        header[0].markdown("**Unit**")
        header[1].markdown("**Status**")
        header[2].markdown("**Days Vacant**")
        header[3].markdown("**Move-In**")
        header[4].markdown("**Alert**")
        st.divider()

        for _, row in filtered.iterrows():

            with st.container():
                cols = st.columns([1.2, 1.5, 1.2, 1.2, 1.5])

                cols[0].markdown(f"**{row['Unit']}**")
                cols[1].markdown(f"{row['Status']}")
                cols[2].markdown(
                    f"<span style='font-size:1.1em'>{row['DV']}</span>",
                    unsafe_allow_html=True
                )
                cols[3].markdown(f"{row['Move_in_fmt']}")
                cols[4].markdown(f"{row['Attention_Badge']}")

                st.divider()

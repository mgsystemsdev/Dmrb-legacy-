import streamlit as st

from ui.logic.filters import (
    filter_by_phase,
    filter_by_status,
    filter_by_nvm,
    normalize_excel_dates,
)

from ui.logic.filter_controls import render_filter_controls


def render(df):

    st.title("Full Table View")

    selected_phase, selected_status, selected_nvm = \
        render_filter_controls(df, key_prefix="ftv")

    filtered = df.copy()
    filtered = filter_by_phase(filtered, selected_phase)
    filtered = filter_by_status(filtered, selected_status)
    filtered = filter_by_nvm(filtered, selected_nvm)
    filtered = normalize_excel_dates(filtered)

    st.markdown(f"**{len(filtered)} units**")
    st.dataframe(filtered, use_container_width=True, height=650)

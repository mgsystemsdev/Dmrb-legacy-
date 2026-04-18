"""Repair Reports screen — Missing Move-Out + FAS Tracker."""

from __future__ import annotations

import streamlit as st

from ui.screens.import_reports import render_missing_move_out, render_fas_tracker


def render_repair_reports() -> None:
    st.title("Repair Reports")

    property_id = st.session_state.get("property_id")
    if property_id is None:
        st.info("Create a property in the Admin tab to begin.")
        return

    tab1, tab2 = st.tabs(["Missing Move-Out", "FAS Tracker"])

    with tab1:
        render_missing_move_out(property_id)

    with tab2:
        render_fas_tracker(property_id)

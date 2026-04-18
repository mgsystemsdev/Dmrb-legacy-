"""Add Turnover screen — manual turnover creation for a unit."""

from __future__ import annotations

import streamlit as st

from services import property_service, turnover_service
from services.turnover_service import TurnoverError


def render_add_turnover() -> None:
    st.title("Add Turnover")

    property_id = st.session_state.get("property_id")
    if property_id is None:
        st.warning("No property selected. Please select a property first.")
        return

    if st.button("← Back to Board"):
        st.session_state["current_page"] = "board"
        st.rerun()

    # ── Cascading selectors ──────────────────────────────────────────────
    phases = property_service.get_phases(property_id)
    if not phases:
        st.info("No phases configured for this property.")
        return

    phase_labels = [p.get("name") or p["phase_code"] for p in phases]
    phase_idx = st.selectbox("Phase", range(len(phases)), format_func=lambda i: phase_labels[i])
    selected_phase = phases[phase_idx]

    buildings = property_service.get_buildings(selected_phase["phase_id"])
    if not buildings:
        st.info("No buildings in the selected phase.")
        return

    building_labels = [b.get("name") or b["building_code"] for b in buildings]
    building_idx = st.selectbox("Building", range(len(buildings)), format_func=lambda i: building_labels[i])
    selected_building = buildings[building_idx]

    units = property_service.get_units_by_building(property_id, selected_building["building_id"])
    if not units:
        st.info("No active units in the selected building.")
        return

    unit_labels = [u["unit_code_norm"] for u in units]
    unit_idx = st.selectbox("Unit", range(len(units)), format_func=lambda i: unit_labels[i])
    selected_unit = units[unit_idx]

    # ── Creation form ────────────────────────────────────────────────────
    with st.form(key="add_turnover_form"):
        move_out = st.date_input("Move-out Date")
        move_in = st.date_input("Move-in Date (optional)", value=None)
        submitted = st.form_submit_button("Create Turnover")

    if submitted:
        try:
            new = turnover_service.create_turnover(
                property_id,
                selected_unit["unit_id"],
                move_out,
                move_in_date=move_in,
                actor="manager",
            )
            st.success(f"Turnover #{new['turnover_id']} created for unit **{selected_unit['unit_code_norm']}**.")
            st.session_state.selected_turnover_id = new["turnover_id"]
            st.session_state.current_page = "unit_detail"
            st.rerun()
        except TurnoverError as exc:
            st.warning(str(exc))

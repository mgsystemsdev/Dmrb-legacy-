"""Property Structure screen — read-only viewer of the property hierarchy."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services import board_service, property_service, scope_service
from ui.helpers.formatting import status_label, qc_label


@st.cache_data(ttl=60)
def _load_phases(property_id: int) -> list[dict]:
    return property_service.get_phases(property_id)


@st.cache_data(ttl=60)
def _load_buildings(phase_id: int) -> list[dict]:
    return property_service.get_buildings(phase_id)


@st.cache_data(ttl=60)
def _load_units(property_id: int, building_id: int) -> list[dict]:
    return property_service.get_units_by_building(property_id, building_id, active_only=False)


def render_property_structure() -> None:
    st.title("🏗️ Property Structure")

    property_id = st.session_state.get("property_id")
    if property_id is None:
        st.warning("No property selected. Please select a property first.")
        return

    tab_structure, tab_turnovers = st.tabs(["Structure", "Turnovers"])

    with tab_structure:
        _render_structure(property_id)

    with tab_turnovers:
        _render_turnovers(property_id)


def _render_structure(property_id: int) -> None:
    phases = _load_phases(property_id)
    uid = int(st.session_state.get("user_id") or 0)
    phase_scope_ids = set(scope_service.get_phase_scope(uid, property_id))
    if phase_scope_ids:
        phases = [p for p in phases if p["phase_id"] in phase_scope_ids]
    if not phases:
        st.info("No phases configured for this property.")
        return

    for phase in phases:
        phase_label = phase.get("name") or phase["phase_code"]
        with st.expander(f"📁 {phase_label}", expanded=False):
            buildings = _load_buildings(phase["phase_id"])
            if not buildings:
                st.caption("No buildings in this phase.")
                continue

            for building in buildings:
                building_label = building.get("name") or building["building_code"]
                with st.expander(f"🏢 {building_label}", expanded=False):
                    units = _load_units(property_id, building["building_id"])
                    if not units:
                        st.caption("No units in this building.")
                        continue

                    for unit in units:
                        active = "✅" if unit.get("is_active") else "❌"
                        carpet = "Yes" if unit.get("has_carpet") else "No"
                        wd = "Yes" if unit.get("has_wd_expected") else "No"

                        with st.container(border=True):
                            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                            c1.write(f"**{unit['unit_code_norm']}**")
                            c2.write(f"Active: {active}")
                            c3.write(f"Carpet: {carpet}")
                            c4.write(f"W/D: {wd}")


def _render_turnovers(property_id: int) -> None:
    uid = int(st.session_state.get("user_id") or 0)
    phase_scope = scope_service.get_phase_scope(uid, property_id)
    board = board_service.get_board_view(property_id, phase_scope=phase_scope, user_id=uid)
    if not board:
        st.info("No open turnovers for the active property.")
        return

    rows = []
    for item in board:
        unit = item.get("unit") or {}
        turnover = item["turnover"]
        tasks = item.get("tasks", [])
        rows.append({
            "Unit": unit.get("unit_code_norm", "—"),
            "Active": "✅" if unit.get("is_active") else "❌",
            "Carpet": "Yes" if unit.get("has_carpet") else "No",
            "W/D": "Yes" if unit.get("has_wd_expected") else "No",
            "Status": (turnover.get("availability_status") or "").capitalize()
            or status_label(turnover.get("lifecycle_phase", "")),
            "DV": turnover.get("days_since_move_out", 0),
            "DTBR": turnover.get("days_to_be_ready", 0),
            "QC": qc_label(tasks),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, height=35 * len(df) + 40, use_container_width=True, hide_index=True)

"""Risk Radar screen — units most likely to miss readiness or move-in deadlines.

Filter row, 4 metrics, read-only risk table sorted by score descending.
Uses risk_service.get_risk_dashboard for all risk scoring (no business logic in UI).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services import property_service, risk_service, scope_service
from ui.helpers.formatting import format_date


_RISK_LEVELS = ["HIGH", "MEDIUM", "LOW"]


@st.cache_data(ttl=30)
def _load_risk_dashboard(property_id: int, phase_scope: tuple[int, ...]) -> list[dict]:
    return risk_service.get_risk_dashboard(
        property_id, phase_scope=list(phase_scope) if phase_scope else None
    )


def render_risk_radar() -> None:
    st.subheader("Turnover Risk Radar")
    st.caption("Units most likely to miss readiness or move-in deadlines.")

    property_id = st.session_state.get("property_id")
    if property_id is None:
        st.info("Create a property in the Admin tab to begin.")
        return

    st.caption(f"Active Property: **{_property_name(property_id)}**")

    phase_scope = scope_service.get_phase_scope(property_id)
    cache_key_scope = tuple(sorted(phase_scope))
    rows = _load_risk_dashboard(property_id, cache_key_scope)
    phase_scope_ids = set(phase_scope)
    all_phases = property_service.get_phases(property_id)
    scoped_phases = [p for p in all_phases if p["phase_id"] in phase_scope_ids]
    phase_codes = [p["phase_code"] for p in scoped_phases]
    phase_map = {p["phase_code"]: p["phase_id"] for p in scoped_phases}
    rows.sort(key=lambda r: r["risk_score"], reverse=True)

    # ── Filter row ───────────────────────────────────────────────────────
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        sel_phases = st.multiselect("Phase", phase_codes, default=[], key="rr_phase",
                                    placeholder="All")
    with c2:
        sel_level = st.selectbox(
            "Risk Level", ["All"] + _RISK_LEVELS, index=0, key="rr_level",
        )
    with c3:
        search = st.text_input("Unit Search", value="", key="rr_search")

    # Apply filters
    if sel_phases:
        sel_pids = {phase_map[c] for c in sel_phases if c in phase_map}
        rows = [r for r in rows if r.get("phase_id") in sel_pids]

    if sel_level != "All":
        rows = [r for r in rows if r["risk_level"] == sel_level]

    if search:
        norm = search.strip().upper()
        rows = [r for r in rows if norm in r["unit_code"]]

    # ── Metrics row ──────────────────────────────────────────────────────
    high = sum(1 for r in rows if r["risk_level"] == "HIGH")
    med = sum(1 for r in rows if r["risk_level"] == "MEDIUM")
    low = sum(1 for r in rows if r["risk_level"] == "LOW")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Active Turnovers", len(rows))
    m2.metric("High Risk", high)
    m3.metric("Medium Risk", med)
    m4.metric("Low Risk", low)

    if not rows:
        st.info("No turnovers match current Risk Radar filters.")
        return

    # ── Read-only table ──────────────────────────────────────────────────
    table = [
        {
            "Unit": r["unit_code"],
            "Phase": r["phase_code"],
            "Risk Level": _risk_display(r["risk_level"]),
            "Risk Score": r["risk_score"],
            "Risk Reasons": ", ".join(r["risk_reasons"]),
            "Move-in Date": format_date(r["move_in_date"]),
        }
        for r in rows
    ]
    st.dataframe(
        pd.DataFrame(table),
        height=35 * len(table) + 40,
        use_container_width=True,
        hide_index=True,
    )


def _risk_display(level: str) -> str:
    if level == "HIGH":
        return "🔴 HIGH"
    if level == "MEDIUM":
        return "🟠 MEDIUM"
    return "🟢 LOW"


@st.cache_data(ttl=60)
def _property_name(property_id: int) -> str:
    props = property_service.get_all_properties()
    for p in props:
        if p["property_id"] == property_id:
            return p["name"]
    return f"Property {property_id}"

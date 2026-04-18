"""
Page 4 — Risk Radar (skeleton).
Layout-only: subheader, caption, filter row (Phase, Risk Level, Unit Search), 4 metrics, read-only table.
Placeholder data only. Run standalone: streamlit run docs/skeleton_pages/page_04_risk_radar.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st


def _placeholder_has_active_property() -> bool:
    return True


def _placeholder_rows():
    """List of risk row dicts: unit_code, phase_code, risk_level, risk_score, risk_reasons, move_in_date. Empty → no rows."""
    return [
        {
            "unit_code": "5-1-101",
            "phase_code": "5",
            "risk_level": "HIGH",
            "risk_score": 85,
            "risk_reasons": ["SLA breach", "DV > 7"],
            "move_in_date": "03/20/2025",
        },
        {
            "unit_code": "7-2-205",
            "phase_code": "7",
            "risk_level": "MEDIUM",
            "risk_score": 55,
            "risk_reasons": ["Move-in soon"],
            "move_in_date": "03/22/2025",
        },
        {
            "unit_code": "8-1-102",
            "phase_code": "8",
            "risk_level": "LOW",
            "risk_score": 20,
            "risk_reasons": [],
            "move_in_date": "04/01/2025",
        },
    ]


def _risk_display(level: str) -> str:
    if level == "HIGH":
        return "🔴 HIGH"
    if level == "MEDIUM":
        return "🟠 MEDIUM"
    return "🟢 LOW"


def render() -> None:
    st.subheader("Turnover Risk Radar")
    st.caption("Units most likely to miss readiness or move-in deadlines.")

    if not _placeholder_has_active_property():
        st.info("Create a property in the Admin tab to begin.")
        return
    st.caption("Active Property: **Sample Property**")

    # ---------- Filter row: Phase | Risk Level | Unit Search (columns 1, 1, 2) ----------
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        st.selectbox("Phase", ["All", "5", "7", "8"], index=0, key="sk_rr_phase")
    with c2:
        st.selectbox("Risk Level", ["All", "HIGH", "MEDIUM", "LOW"], index=0, key="sk_rr_level")
    with c3:
        st.text_input("Unit Search", value="", key="sk_rr_search")

    rows = _placeholder_rows()
    all_rows = rows  # skeleton: no filtering by risk level
    high_count = sum(1 for r in all_rows if r.get("risk_level") == "HIGH")
    med_count = sum(1 for r in all_rows if r.get("risk_level") == "MEDIUM")
    low_count = sum(1 for r in all_rows if r.get("risk_level") == "LOW")

    # ---------- Metrics row: 4 columns ----------
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Active Turnovers", len(all_rows))
    m2.metric("High Risk", high_count)
    m3.metric("Medium Risk", med_count)
    m4.metric("Low Risk", low_count)

    if not rows:
        st.info("No turnovers match current Risk Radar filters.")
        return

    # ---------- Read-only table ----------
    radar_table = [
        {
            "Unit": r.get("unit_code") or "",
            "Phase": r.get("phase_code") or "",
            "Risk Level": _risk_display(r.get("risk_level") or "LOW"),
            "Risk Score": r.get("risk_score") or 0,
            "Risk Reasons": ", ".join(r.get("risk_reasons") or []),
            "Move-in Date": r.get("move_in_date") or "",
        }
        for r in rows
    ]
    st.dataframe(
        pd.DataFrame(radar_table),
        use_container_width=True,
        hide_index=True,
    )


if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Risk Radar (skeleton)")
    render()

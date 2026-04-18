"""
Sidebar skeleton.
Layout-only: title, caption, navigation radio, divider, Top Flags (expanders + unit buttons).
Placeholder data only; no backend. Run standalone to preview the left rail.
"""
from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Placeholder: what the sidebar shows below the divider
# ---------------------------------------------------------------------------
def _placeholder_db_available() -> bool:
    return True  # Set False to show "Database not available" in sidebar


def _placeholder_flag_categories():
    """List of (expandable_title, list of button_labels). Empty list → show 'No flagged units'."""
    return [
        ("📋 Insp Breach (2)", ["5-1-101 · DV 12", "7-2-205 · DV 8"]),
        ("⚠ SLA Breach (1)", ["5-1-101 · DV 12"]),
        ("🔴 SLA MI Breach (0)", []),
        ("📅 Plan Breach (0)", []),
    ]
    # To see "No flagged units" state, return [] and set any_flags = False in render.


# ---------------------------------------------------------------------------
# Render sidebar only
# ---------------------------------------------------------------------------
def render_sidebar() -> None:
    st.sidebar.title("The DMRB")
    st.sidebar.caption("Apartment Turn Tracker")

    nav_labels = [
        "Morning Workflow",
        "DMRB Board",
        "Flag Bridge",
        "Risk Radar",
        "Report Operations",
        "Turnover Detail",
        "DMRB AI Agent",
        "Admin",
    ]
    st.sidebar.radio(
        "Navigate",
        nav_labels,
        index=1,  # DMRB Board selected
        key="sidebar_nav",
    )

    st.sidebar.divider()
    st.sidebar.markdown("**Top Flags**")

    if not _placeholder_db_available():
        st.sidebar.error("Database not available")
        return

    categories = _placeholder_flag_categories()
    any_flags = any(buttons for _, buttons in categories)

    if not any_flags:
        st.sidebar.caption("No flagged units")
        return

    for i, (expander_title, button_labels) in enumerate(categories):
        with st.sidebar.expander(expander_title):
            for j, label in enumerate((button_labels or [])[:5]):
                st.button(label, key=f"sb_flag_{i}_{j}")


def render() -> None:
    render_sidebar()
    # Main area: minimal placeholder so the app has something to show
    st.caption("Sidebar skeleton — select a page from the left. Main content is loaded by the full app.")


if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="The DMRB — Sidebar (skeleton)")
    render()

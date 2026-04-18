import streamlit as st

from services import board_service


def render_filters() -> None:
    opts = board_service.get_board_filter_options()
    priority_order = opts["priority_order"]
    phase_order = opts["phase_order"]
    readiness_states = opts["readiness_states"]

    filters = st.session_state.get("board_filters", {
        "priority": "All",
        "phase": "All",
        "readiness": "All",
    })

    with st.form("board_filters_form"):
        col1, col2, col3 = st.columns(3)

        with col1:
            priority = st.selectbox(
                "Priority",
                options=["All"] + priority_order,
                index=(["All"] + priority_order).index(filters.get("priority", "All")),
            )
        with col2:
            phase = st.selectbox(
                "Phase",
                options=["All"] + phase_order,
                index=(["All"] + phase_order).index(filters.get("phase", "All")),
            )
        with col3:
            readiness = st.selectbox(
                "Readiness",
                options=["All"] + readiness_states,
                index=(["All"] + readiness_states).index(filters.get("readiness", "All")),
            )

        if st.form_submit_button("Apply Filters"):
            st.session_state.board_filters = {
                "priority": priority,
                "phase": phase,
                "readiness": readiness,
            }


def apply_filters(board: list[dict]) -> list[dict]:
    filters = st.session_state.get("board_filters", {})
    result = board

    priority = filters.get("priority", "All")
    if priority != "All":
        result = [item for item in result if item["priority"] == priority]

    phase = filters.get("phase", "All")
    if phase != "All":
        result = [item for item in result if item["turnover"]["lifecycle_phase"] == phase]

    readiness = filters.get("readiness", "All")
    if readiness != "All":
        result = [item for item in result if item["readiness"]["state"] == readiness]

    return result

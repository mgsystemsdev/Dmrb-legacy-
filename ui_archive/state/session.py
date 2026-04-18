from __future__ import annotations

import streamlit as st


def init_session_state() -> None:
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("access_mode", None)
    st.session_state.setdefault("user_id", None)
    st.session_state.setdefault("username", None)
    st.session_state.setdefault("current_page", "board")
    st.session_state.setdefault("property_id", None)
    st.session_state.setdefault("selected_turnover_id", None)
    st.session_state.setdefault("admin_enable_db_writes", False)
    st.session_state.setdefault(
        "board_filters",
        {"priority": "All", "phase": "All", "readiness": "All"},
    )

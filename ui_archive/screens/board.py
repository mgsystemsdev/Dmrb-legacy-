"""Board screen — main operational board view for a property.

Layout: filter bar → metrics bar → Unit Info / Unit Tasks tabs.
Uses st.data_editor for tabular display with inline editing.
"""

from __future__ import annotations

import streamlit as st

from services import board_service, property_service, scope_service
from ui.components.board_table import render_board_tabs
from ui.state.constants import STATUS_OPTIONS, NVM_OPTS, QC_OPTS


_FILTER_LABELS = {
    "SLA_RISK": "SLA Breach",
    "MOVE_IN_DANGER": "Move-In Danger",
    "INSPECTION_DELAY": "Inspection Breach",
    "PLAN_BREACH": "Plan Blocked",
}


@st.cache_data(ttl=30)
def _load_board(property_id: int, phase_scope: tuple[int, ...]) -> list[dict]:
    return board_service.get_board_view(
        property_id, phase_scope=list(phase_scope) if phase_scope else None
    )


def render_board() -> None:
    property_id = st.session_state.get("property_id")
    if property_id is None:
        st.info("Create a property in the Admin tab to begin.")
        return

    st.caption(f"Active Property: **{_property_name(property_id)}**")

    phase_scope = scope_service.get_phase_scope(property_id)
    cache_key = (property_id, tuple(sorted(phase_scope)))
    full_board = _load_board(property_id, cache_key[1])
    board = full_board

    # ── Flag Bridge filter passthrough ───────────────────────────────────
    board_filter = st.session_state.get("board_filter")
    if board_filter:
        board = board_service.filter_by_flag_category(board, board_filter)
        st.info(f"Showing **{_FILTER_LABELS.get(board_filter, board_filter)}** units only.")
        if st.button("Clear Filter"):
            st.session_state.pop("board_filter", None)
            st.rerun()

    # ── Filter bar ───────────────────────────────────────────────────────
    board = _render_filter_bar(board, property_id)

    # ── Metrics bar (pass already-loaded board to avoid re-fetching) ────
    _render_metrics_bar(full_board)

    if not board:
        st.info("No turnovers match filters.")
        return

    # ── Unit Info / Unit Tasks tabs ──────────────────────────────────────
    render_board_tabs(board)


# ── Filter bar ───────────────────────────────────────────────────────────────

def _render_filter_bar(board: list[dict], property_id: int) -> list[dict]:
    """Render the inline filter bar and return filtered board."""
    from ui.helpers.formatting import nvm_state, qc_label, display_status_for_board_item

    # Collect assignees from board tasks for the filter dropdown
    assignee_set: set[str] = set()
    for item in board:
        for t in item.get("tasks", []):
            a = t.get("assignee")
            if a:
                assignee_set.add(a)
    assignee_opts = ["All"] + sorted(assignee_set)

    with st.container(border=True):
        c0, c1, c2, c3, c4, c5, c6, c7 = st.columns([1.8, 0.9, 1.1, 0.9, 0.9, 0.9, 0.5, 0.5])

        with c0:
            search = st.text_input(
                "Search unit", value="", key="board_search",
                placeholder="e.g. A-101", label_visibility="collapsed",
            )
        with c1:
            phase_scope_ids = set(scope_service.get_phase_scope(property_id))
            all_phases = property_service.get_phases(property_id)
            scoped_phases = [p for p in all_phases if p["phase_id"] in phase_scope_ids]
            phase_codes = [p["phase_code"] for p in scoped_phases]
            phase_map = {p["phase_code"]: p["phase_id"] for p in scoped_phases}
            sel_phases = st.multiselect("Phase", phase_codes, default=[], key="board_phase",
                                        placeholder="All")
        with c2:
            sel_status = st.selectbox(
                "Status", ["All", "Vacant"] + STATUS_OPTIONS, index=0, key="board_status",
            )
        with c3:
            sel_nvm = st.selectbox("N/V/M", NVM_OPTS, index=0, key="board_nvm")
        with c4:
            sel_qc = st.selectbox("QC", QC_OPTS, index=0, key="board_qc")
        with c5:
            sel_assignee = st.selectbox("Assignee", assignee_opts, index=0, key="board_assignee")

        n_active = len(board)
        n_crit = sum(
            1 for item in board
            if item["priority"] in ("MOVE_IN_DANGER", "SLA_RISK")
        )
        c6.metric("Active", n_active)
        c7.metric("CRIT", n_crit)

    # Apply filters
    if search:
        norm = search.strip().upper()
        board = [
            item for item in board
            if item.get("unit") and norm in item["unit"]["unit_code_norm"]
        ]

    if sel_phases:
        sel_pids = {phase_map[c] for c in sel_phases if c in phase_map}
        board = [
            item for item in board
            if item.get("unit") and item["unit"].get("phase_id") in sel_pids
        ]

    if sel_status != "All":
        if sel_status == "Vacant":
            _status_match = {"Vacant ready", "Vacant not ready"}
        else:
            _status_match = {sel_status}
        board = [
            item for item in board
            if display_status_for_board_item(item) in _status_match
        ]

    if sel_nvm != "All":
        if sel_nvm == "Notice":
            _nvm_match = {"Notice", "Notice + SMI"}
        elif sel_nvm == "SMI":
            _nvm_match = {"SMI"}
        else:
            _nvm_match = {sel_nvm}
        board = [
            item for item in board
            if nvm_state(item["turnover"]) in _nvm_match
        ]

    if sel_qc != "All":
        _qc_done = sel_qc == "QC Done"
        board = [
            item for item in board
            if (qc_label(item.get("tasks", [])) == "QC Done") == _qc_done
        ]

    if sel_assignee != "All":
        board = [
            item for item in board
            if any(t.get("assignee") == sel_assignee for t in item.get("tasks", []))
        ]

    return board


# ── Metrics bar ──────────────────────────────────────────────────────────────

def _render_metrics_bar(board: list[dict]) -> None:
    """Render headline metrics from board_service read model (no local computation)."""
    metrics = board_service.get_board_metrics(board=board)
    with st.container(border=True):
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Active Units", metrics["active"])
        m2.metric("Violations", metrics["violations"])
        m3.metric("Plan Breach", metrics["plan_breach"])
        m4.metric("SLA Breach", metrics["sla_breach"])
        m5.metric("Move-In Risk", metrics["move_in_risk"])
        m6.metric("Work Stalled", metrics["work_stalled"])


# ── Helpers ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _property_name(property_id: int) -> str:
    props = property_service.get_all_properties()
    for p in props:
        if p["property_id"] == property_id:
            return p["name"]
    return f"Property {property_id}"

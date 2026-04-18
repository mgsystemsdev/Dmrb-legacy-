"""Flag Bridge screen — breach-focused dashboard with filter/metrics bars
and a single read-only breach table using st.data_editor."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services import board_service, property_service, scope_service
from ui.helpers.formatting import (
    format_completed_date,
    nvm_state,
    display_status_for_board_item,
)
from ui.state.constants import EXEC_MAP, STATUS_OPTIONS, NVM_OPTS, BRIDGE_OPTS, VALUE_OPTS


@st.cache_data(ttl=30)
def _load_board(property_id: int, phase_scope: tuple[int, ...]) -> list[dict]:
    return board_service.get_board_view(
        property_id, phase_scope=list(phase_scope) if phase_scope else None
    )


def render_flag_bridge() -> None:
    property_id = st.session_state.get("property_id")
    if property_id is None:
        st.info("Create a property in the Admin tab to begin.")
        return

    st.caption(f"Active Property: **{_property_name(property_id)}**")

    phase_scope = scope_service.get_phase_scope(property_id)
    board = _load_board(property_id, tuple(sorted(phase_scope)))

    # ── Filter row ───────────────────────────────────────────────────────
    board = _render_filter_bar(board, property_id)

    # ── Metrics row ──────────────────────────────────────────────────────
    _render_metrics_bar(board)

    if not board:
        st.info("No rows match filters.")
        return

    # ── Breach table ─────────────────────────────────────────────────────
    _render_breach_table(board)


# ── Filter bar ───────────────────────────────────────────────────────────────

def _render_filter_bar(board: list[dict], property_id: int) -> list[dict]:
    # Collect assignees from board tasks for the filter dropdown
    assignee_set: set[str] = set()
    for item in board:
        for t in item.get("tasks", []):
            a = t.get("assignee")
            if a:
                assignee_set.add(a)
    assignee_opts = ["All"] + sorted(assignee_set)

    with st.container(border=True):
        c0, c1, c2, c3, c4, c5 = st.columns(6)

        with c0:
            phase_scope_ids = set(scope_service.get_phase_scope(property_id))
            all_phases = property_service.get_phases(property_id)
            scoped_phases = [p for p in all_phases if p["phase_id"] in phase_scope_ids]
            phase_codes = [p["phase_code"] for p in scoped_phases]
            phase_map = {p["phase_code"]: p["phase_id"] for p in scoped_phases}
            sel_phases = st.multiselect("Phase", phase_codes, default=[], key="fb_phase",
                                        placeholder="All")
        with c1:
            sel_status = st.selectbox(
                "Status", ["All", "Vacant"] + STATUS_OPTIONS, index=0, key="fb_status",
            )
        with c2:
            sel_nvm = st.selectbox("N/V/M", NVM_OPTS, index=0, key="fb_nvm")
        with c3:
            sel_assignee = st.selectbox("Assignee", assignee_opts, index=0, key="fb_assignee")
        with c4:
            sel_bridge = st.selectbox("Flag Bridge", BRIDGE_OPTS, index=0, key="fb_bridge")
        with c5:
            sel_value = st.selectbox("Value", VALUE_OPTS, index=0, key="fb_value")

    # Apply filters
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

    if sel_assignee != "All":
        board = [
            item for item in board
            if any(t.get("assignee") == sel_assignee for t in item.get("tasks", []))
        ]

    if sel_bridge != "All":
        board = _filter_by_bridge(board, sel_bridge)

    if sel_value != "All":
        want = sel_value == "Yes"
        board = [item for item in board if board_service.has_any_breach(item) == want]

    return board


# ── Metrics bar ──────────────────────────────────────────────────────────────

def _render_metrics_bar(board: list[dict]) -> None:
    """Render metrics from board_service read model (no local computation)."""
    metrics = board_service.get_flag_bridge_metrics(board)
    with st.container(border=True):
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Units", metrics["total"])
        m2.metric("Violations", metrics["violations"])
        m3.metric("Units w/ Breach", metrics["units_with_breach"])


# ── Breach table ─────────────────────────────────────────────────────────────

def _render_breach_table(board: list[dict]) -> None:
    tid_list: list[int] = []
    rows: list[dict] = []

    for item in board:
        turnover = item["turnover"]
        unit = item.get("unit")
        tid_list.append(turnover["turnover_id"])

        unit_code = unit["unit_code_norm"] if unit else "—"

        bd = board_breach_row_display(item)

        ready_date = format_completed_date(turnover.get("report_ready_date"))
        tasks = list(item.get("tasks") or [])
        inspection_task = next(
            (t for t in tasks if t.get("task_type") in BOARD_INSPECTION_TASK_TYPES),
            None,
        )
        inspection_execution = (
            EXEC_MAP.get(inspection_task["execution_status"], inspection_task["execution_status"])
            if inspection_task
            else "—"
        )

        status_display = display_status_for_board_item(item)

        def _dot(red: bool) -> str:
            return "🔴" if red else "🟢"

        rows.append({
            "▶": False,
            "Unit": unit_code,
            "Status": status_display,
            "DV": turnover.get("days_since_move_out") or 0,
            "Move-In": format_completed_date(turnover.get("move_in_date")),
            "Ready Date": ready_date,
            "Inspection": inspection_execution,
            "Alert": bd.alert_display,
            "Viol": _dot(bd.is_viol),
            "Insp": bd.insp_display,
            "SLA": _dot(bd.is_sla),
            "MI": bd.mi_display,
            "Plan": _dot(bd.is_plan),
        })

    df = pd.DataFrame(rows)

    edited = st.data_editor(
        df,
        height=35 * len(df) + 40,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=["Unit", "Status", "DV", "Move-In", "Ready Date", "Alert", "Viol", "Insp", "Inspection", "SLA", "MI", "Plan"],
        column_config={
            "▶": st.column_config.CheckboxColumn("▶", width=40),
            "Unit": st.column_config.TextColumn("Unit"),
            "Status": st.column_config.TextColumn("Status"),
            "DV": st.column_config.NumberColumn("DV", width=50),
            "Move-In": st.column_config.TextColumn("Move-In"),
            "Ready Date": st.column_config.TextColumn("Ready Date", width=90),
            "Alert": st.column_config.TextColumn("Alert", width=50),
            "Viol": st.column_config.TextColumn("Viol", width=50),
            "Insp": st.column_config.TextColumn("Insp", width=50),
            "Inspection": st.column_config.TextColumn("Insp", width=100),
            "SLA": st.column_config.TextColumn("SLA", width=50),
            "MI": st.column_config.TextColumn("MI", width=50),
            "Plan": st.column_config.TextColumn("Plan", width=50),
        },
        column_order=["▶", "Unit", "Status", "DV", "Move-In", "Ready Date", "Inspection", "Alert", "Viol", "Insp", "SLA", "MI", "Plan"],
        key="fb_editor",
    )

    # Handle row selection
    if "▶" in edited.columns:
        selected = edited[edited["▶"] == True]  # noqa: E712
        if not selected.empty:
            idx = selected.index[0]
            if idx < len(tid_list):
                st.session_state.selected_turnover_id = tid_list[idx]
                st.session_state.current_page = "unit_detail"
                st.rerun()


# ── Helpers ──────────────────────────────────────────────────────────────────

_BRIDGE_MAP = {
    "Insp Breach": "INSPECTION_DELAY",
    "SLA Breach": "SLA",
    "SLA MI Breach": "MI",
    "Plan Breach": "PLAN",
}


def _item_has_inspection_breach(item: dict) -> bool:
    """True if this item should be shown when filtering by Insp Breach.
    Matches agreement RED/YELLOW and the table's Insp column logic (Vacant not ready + inspection not done + dv)."""
    agreements = item.get("agreements") or {}
    insp_flag = agreements.get("inspection")
    if insp_flag in ("RED", "YELLOW"):
        return True
    if not agreements and item.get("priority") == "INSPECTION_DELAY":
        return True
    # Table shows 🔴/🟡 for "Vacant not ready" when inspection not done and dv > 0
    status_display = display_status_for_board_item(item)
    if status_display != "Vacant not ready":
        return False
    tasks = item.get("tasks", [])
    inspection_task = next(
        (t for t in tasks if t.get("task_type") in BOARD_INSPECTION_TASK_TYPES),
        None,
    )
    if inspection_task and inspection_task.get("execution_status") == "COMPLETED":
        return False
    dv = (item.get("turnover") or {}).get("days_since_move_out")
    dv_days = dv if dv is not None else 0
    return dv_days > 0


def _filter_by_bridge(board: list[dict], sel: str) -> list[dict]:
    """Filter by Flag Bridge category. Uses item agreements when present (Phase 4)."""
    if sel == "Insp Breach":
        return [i for i in board if _item_has_inspection_breach(i)]
    if sel == "SLA Breach":
        return [
            i for i in board
            if (i.get("agreements") or {}).get("sla") == "RED"
            or (
                not i.get("agreements")
                and (i["priority"] == "SLA_RISK" or i["sla"]["risk_level"] in ("WARNING", "BREACH"))
            )
        ]
    if sel == "SLA MI Breach":
        return [
            i for i in board
            if (i.get("agreements") or {}).get("move_in") == "RED"
            or (not i.get("agreements") and (i["sla"].get("move_in_pressure") or 999) <= 3)
        ]
    if sel == "Plan Breach":
        return [
            i for i in board
            if (i.get("agreements") or {}).get("plan") == "RED"
            or (
                not i.get("agreements")
                and i["readiness"]["state"] == "BLOCKED"
                and i["priority"] not in ("MOVE_IN_DANGER", "SLA_RISK")
            )
        ]
    return board


@st.cache_data(ttl=60)
def _property_name(property_id: int) -> str:
    props = property_service.get_all_properties()
    for p in props:
        if p["property_id"] == property_id:
            return p["name"]
    return f"Property {property_id}"

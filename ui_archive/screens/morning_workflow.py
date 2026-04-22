"""Morning Workflow screen — daily operational checklist.

Layout: top actions → yesterday's work → plan today's work → import-status bar
→ board priority → risk metrics bar → missing-move-out table → critical-units table
→ today's work (last).
Answers: "What do I need to fix right now before the day starts?"
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from services import (
    board_service,
    import_service,
    property_service,
    scope_service,
    task_service,
    turnover_service,
)
from services.report_operations import missing_move_out_service
from ui.helpers.formatting import format_date
from ui.state.constants import TASK_DISPLAY, TASK_PIPELINE_ORDER


_REPORT_LABELS = {
    "MOVE_OUTS": "Move-Out",
    "PENDING_MOVE_INS": "Move-In",
    "AVAILABLE_UNITS": "Available",
    "PENDING_FAS": "FAS",
}

# Board priority tiers (domain keys) → Morning Workflow summary labels (matches board row priorities)
_BOARD_PRIORITY_SUMMARY = (
    ("MOVE_IN_DANGER", "CRITICAL", "Move-in danger"),
    ("SLA_RISK", "URGENT", "SLA risk"),
    ("INSPECTION_DELAY", "HIGH", "Inspection delay"),
)

_STABLE_TOP_ACTION = "No urgent actions — system is stable"


def _import_timestamp_is_today(ts: str, today: date) -> bool:
    """True if the batch timestamp falls on the local calendar day ``today``."""
    try:
        s = ts.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.date() == today
    except (ValueError, TypeError, OSError):
        return False


def _render_top_actions(property_id: int, today: date, phase_scope: list[int], user_id: int) -> None:
    """Highest-priority directives from existing board summary + missing move-out list (no new services)."""
    summary = board_service.get_board_summary(
        property_id, today=today, phase_scope=phase_scope, user_id=user_id
    )
    bp = summary.get("by_priority") or {}
    crit = int(bp.get("MOVE_IN_DANGER", 0))
    urgent = int(bp.get("SLA_RISK", 0))
    has_missing = bool(missing_move_out_service.list_missing_move_outs(property_id, user_id=user_id))

    messages: list[str] = []
    if crit > 0:
        messages.append("Resolve move-in danger units immediately")
    elif urgent > 0:
        messages.append("Address SLA risk units")
    elif has_missing:
        messages.append("Fix missing move-outs")
    else:
        messages.append(_STABLE_TOP_ACTION)

    # Up to two more directives when multiple signals still apply (cap 3 total)
    if messages[0] != _STABLE_TOP_ACTION:
        if crit > 0 and urgent > 0 and "Address SLA risk units" not in messages:
            messages.append("Address SLA risk units")
        if has_missing and "Fix missing move-outs" not in messages:
            messages.append("Fix missing move-outs")
        messages = messages[:3]

    with st.container(border=True):
        st.markdown("**Top actions**")
        for i, text in enumerate(messages, start=1):
            label = f"{i}. {text}"
            if text == _STABLE_TOP_ACTION:
                st.markdown(label)
            elif text == "Resolve move-in danger units immediately":
                if st.button(label, key=f"mw_top_{i}_mid", use_container_width=True):
                    st.session_state.board_filter = "MOVE_IN_DANGER"
                    st.session_state.current_page = "board"
                    st.rerun()
            elif text == "Address SLA risk units":
                if st.button(label, key=f"mw_top_{i}_sla", use_container_width=True):
                    st.session_state.board_filter = "SLA_RISK"
                    st.session_state.current_page = "board"
                    st.rerun()
            elif text == "Fix missing move-outs":
                if st.button(label, key=f"mw_top_{i}_mm", use_container_width=True):
                    st.session_state.mw_focus_repair_queue = True
                    st.session_state.current_page = "morning_workflow"
                    st.rerun()
            else:
                st.markdown(label)


def _render_yesterdays_work(
    property_id: int, today: date, phase_scope: list[int], user_id: int
) -> None:
    rows = task_service.get_yesterday_completions(
        property_id, phase_scope=phase_scope, today=today, user_id=user_id
    )
    with st.container(border=True):
        st.markdown("**Yesterday's Work — verify completion**")
        if not rows:
            st.caption("No tasks completed yesterday")
            return
        by_unit: dict[str, list[dict]] = {}
        for r in rows:
            code = r["unit_code"] or "?"
            by_unit.setdefault(code, []).append(r)
        for unit_code in sorted(by_unit.keys()):
            st.markdown(f"**Unit {unit_code}**")
            for t in by_unit[unit_code]:
                who = t.get("assignee")
                line = f"✓ {t['task_type']}"
                if who:
                    line += f" — {who}"
                st.markdown(line)


def _task_due_today(row: dict, today: date) -> bool:
    """Match Ops Schedule: primary date is vendor_due_date; else scheduled_date when due is unset."""
    vd = row.get("vendor_due_date")
    if vd == today:
        return True
    if vd is None and row.get("scheduled_date") == today:
        return True
    return False


def _todays_work_column_count(n_types: int) -> int:
    """Use 3–5 columns based on how many task types are present."""
    if n_types <= 3:
        return 3
    if n_types == 4:
        return 4
    return 5


def _render_todays_work(
    property_id: int, today: date, phase_scope: list[int], user_id: int
) -> None:
    rows = task_service.get_schedule_rows(
        property_id, phase_scope=phase_scope, user_id=user_id
    )
    due = [r for r in rows if _task_due_today(r, today)]
    with st.container(border=True):
        st.markdown("**Today's Work — execute**")
        if not due:
            st.caption("No tasks due today")
            return
        by_type: dict[str, list[str]] = {}
        for r in due:
            tt = r["task_type"]
            uc = r["unit_code"] or "?"
            by_type.setdefault(tt, []).append(uc)
        order = {t: i for i, t in enumerate(TASK_PIPELINE_ORDER)}
        ordered_types = sorted(
            by_type.keys(), key=lambda t: (order.get(t, len(order)), t)
        )
        n_types = len(ordered_types)
        num_cols = _todays_work_column_count(n_types)

        row_start = 0
        row_idx = 0
        while row_start < n_types:
            if row_idx > 0:
                st.markdown("")
            chunk = ordered_types[row_start : row_start + num_cols]
            cols = st.columns(num_cols)
            for col, tt in zip(cols, chunk):
                label = TASK_DISPLAY.get(tt, tt)
                with col:
                    with st.container(border=True):
                        st.markdown(f"**{label}**")
                        for unit_code in sorted(set(by_type[tt])):
                            st.markdown(f"Unit {unit_code}")
            row_start += num_cols
            row_idx += 1


def _render_plan_todays_work_nav() -> None:
    """Navigate to Operations Schedule (navigation only; no filters)."""
    if st.button("Plan today's work", key="mw_plan_todays_work", use_container_width=True):
        st.session_state.current_page = "operations_schedule"
        st.rerun()


def render_morning_workflow() -> None:
    property_id = st.session_state.get("property_id")
    if property_id is None:
        st.info("Create a property in the Admin tab to begin.")
        return

    st.caption(f"Active Property: **{_property_name(property_id)}**")

    today = date.today()
    uid = int(st.session_state.get("user_id") or 0)
    phase_scope = scope_service.get_phase_scope(uid, property_id)

    # ── Top actions (compose from board summary + missing move-out queue) ─
    _render_top_actions(property_id, today, phase_scope, uid)

    # ── Yesterday's completions (single query; grouped by unit) ──────────
    _render_yesterdays_work(property_id, today, phase_scope, uid)

    # ── Ops Schedule handoff (after triage) ───────────────────────────────
    _render_plan_todays_work_nav()

    # ── Import status bar ────────────────────────────────────────────────
    _render_import_status(property_id)

    # ── Board priority summary (same counts as board by priority tier) ─
    _render_board_priority_summary(property_id, today, phase_scope, uid)

    # ── Risk metrics bar ─────────────────────────────────────────────────
    _render_risk_metrics(property_id, phase_scope, uid)

    # ── Missing move-out table ───────────────────────────────────────────
    _render_missing_move_out(property_id, today, uid)

    # ── Today's critical units table ─────────────────────────────────────
    critical = board_service.get_todays_critical_units(
        property_id, today=today, phase_scope=phase_scope, user_id=uid
    )
    _render_todays_critical(critical)

    # ── Today's due tasks (last row; same rows as Ops Schedule) ───────────
    _render_todays_work(property_id, today, phase_scope, uid)


# ── Import status bar ────────────────────────────────────────────────────────

def _render_import_status(property_id: int) -> None:
    today = date.today()
    timestamps = import_service.get_latest_import_timestamps(property_id)

    with st.container(border=True):
        cols = st.columns(len(_REPORT_LABELS))
        for col, (key, label) in zip(cols, _REPORT_LABELS.items()):
            ts = timestamps.get(key)
            if ts:
                col.metric(label, ts[:16].replace("T", " "))
                if not _import_timestamp_is_today(ts, today):
                    col.caption(":orange[⚠ Not imported today]")
            else:
                col.metric(label, "—")
                col.caption(":orange[⚠ Not imported today]")


# ── Board priority summary ───────────────────────────────────────────────────

def _render_board_priority_summary(
    property_id: int, today: date, phase_scope: list[int], user_id: int
) -> None:
    """Show top board priority counts from get_board_summary (read-only; matches board page)."""
    summary = board_service.get_board_summary(
        property_id, today=today, phase_scope=phase_scope, user_id=user_id
    )
    by_priority = summary.get("by_priority") or {}
    with st.container(border=True):
        st.caption("**Board priority** — same tiers as the main board")
        cols = st.columns(len(_BOARD_PRIORITY_SUMMARY))
        for col, (pkey, title, sub) in zip(cols, _BOARD_PRIORITY_SUMMARY):
            n = int(by_priority.get(pkey, 0))
            col.metric(title, n)
            col.caption(sub)


# ── Risk metrics bar ─────────────────────────────────────────────────────────

def _render_risk_metrics(property_id: int, phase_scope: list[int], user_id: int) -> None:
    """Render risk metrics from board_service read model (no local computation)."""
    metrics = board_service.get_morning_risk_metrics(
        property_id, phase_scope=phase_scope, user_id=user_id
    )
    vacant_over_7 = metrics["vacant_over_7"]
    sla_breach = metrics["sla_breach"]
    move_in_soon = metrics["move_in_soon"]
    with st.container(border=True):
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Vacant > 7 days", vacant_over_7)
        m2.metric("SLA Breach", sla_breach)
        m3.metric("Move-In ≤ 3 days", move_in_soon)
        if sla_breach > 0:
            with m4:
                if st.button("Flag Bridge", key="mw_flag_bridge"):
                    st.session_state.board_filter = "SLA_RISK"
                    st.session_state.current_page = "flag_bridge"
                    st.rerun()
        with m5:
            if st.button("Open Board", key="mw_board"):
                st.session_state.current_page = "board"
                st.rerun()


# ── Missing move-out table ───────────────────────────────────────────────────

def _render_missing_move_out(property_id: int, today: date, user_id: int) -> None:
    focused = st.session_state.pop("mw_focus_repair_queue", None)
    rows = missing_move_out_service.list_missing_move_outs(property_id, user_id=user_id)
    if focused and rows:
        st.info("**Repair queue** — add move-out dates in the table below.")
    if not rows:
        st.success("No units in repair queue")
        return

    st.caption("**Missing Move-Out** — add a date to create the turnover")

    df = pd.DataFrame([
        {
            "Unit": r.get("unit_code_norm", ""),
            "Move-In": format_date(r.get("move_in_date")),
            "Report": r.get("report_type", "—"),
            "Move-Out": None,
        }
        for r in rows
    ])

    edited = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=["Unit", "Move-In", "Report"],
        column_config={
            "Unit": st.column_config.TextColumn("Unit"),
            "Move-In": st.column_config.TextColumn("Move-In"),
            "Report": st.column_config.TextColumn("Report"),
            "Move-Out": st.column_config.DateColumn("Move-Out", format="MM/DD/YYYY"),
        },
        key="mw_missing_editor",
    )

    created = 0
    for idx, row_data in edited.iterrows():
        if row_data["Move-Out"] is not None and idx < len(rows):
            raw = rows[idx]
            unit = turnover_service.search_unit(property_id, raw["unit_code_norm"])
            if unit is None:
                st.error(f"Unit {raw['unit_code_norm']} not found.")
                continue
            try:
                move_out = row_data["Move-Out"]
                if isinstance(move_out, pd.Timestamp):
                    move_out = move_out.date()
                new = missing_move_out_service.resolve_missing_move_out(
                    row_id=raw["row_id"],
                    property_id=property_id,
                    unit_id=unit["unit_id"],
                    move_out_date=move_out,
                    move_in_date=raw.get("move_in_date"),
                    actor="manager",
                )
                st.success(
                    f"Turnover #{new['turnover_id']} created for "
                    f"**{raw['unit_code_norm']}**."
                )
                created += 1
            except turnover_service.TurnoverError as exc:
                st.error(str(exc))

    if created:
        st.cache_data.clear()
        st.rerun()


# ── Today's critical units table ─────────────────────────────────────────────

def _render_todays_critical(critical: list[dict]) -> None:
    if not critical:
        st.info("No move-ins, move-outs, or ready dates today.")
        return

    st.caption("**Today's Critical Units** — move-ins, move-outs, and ready dates today")

    with st.container(border=True):
        for idx, c in enumerate(critical):
            label = f"{c['unit_code']} — {c['event']} — {c['date']}"
            if st.button(label, key=f"mw_crit_nav_{idx}", use_container_width=True):
                # unit_detail reads turnover id (same pattern as board_table / flag_bridge)
                st.session_state.selected_turnover_id = c["turnover_id"]
                st.session_state.current_page = "unit_detail"
                st.rerun()


# ── Helpers ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _property_name(property_id: int) -> str:
    props = property_service.get_all_properties()
    for p in props:
        if p["property_id"] == property_id:
            return p["name"]
    return f"Property {property_id}"

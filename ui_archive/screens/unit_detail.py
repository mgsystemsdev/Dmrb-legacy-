"""Unit detail screen — full turnover detail view.

Panels: Unit Info → Status & QC → Dates → W/D → Risks →
        Authority (expander) → Tasks → Notes → History (expander).
Matches the skeleton blueprint with real data wired through services.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from domain.availability_status import (
    MANUAL_READY_ON_NOTICE,
    MANUAL_READY_VACANT_NOT_READY,
    MANUAL_READY_VACANT_READY,
)
from services import (
    audit_service,
    note_service,
    property_service,
    risk_service,
    task_service,
    turnover_service,
    unit_service,
)
from services.write_guard import WritesDisabledError
from ui.helpers.formatting import (
    format_date,
    format_completed_date,
    format_datetime,
    status_label,
    nvm_state,
    readiness_badge,
    sla_indicator,
    qc_label,
)
from ui.state.constants import (
    EXEC_LABELS_EXTENDED,
    EXEC_MAP,
    EXEC_REV,
    EXEC_SIDE_EFFECTS,
    BLOCK_OPTIONS,
    STATUS_OPTIONS,
    TASK_DISPLAY,
    CARPET_STATUSES,
    CARPET_ICONS,
    WD_OPTS,
    NOTE_SEVERITIES,
    SEVERITY_ICONS,
    TASK_PIPELINE_ORDER,
)


def _safe_index(opts: list, value: str) -> int:
    try:
        return opts.index(value)
    except (ValueError, TypeError):
        return 0


def _unit_detail_status_to_fields(board_label: str) -> dict[str, object]:
    """Map Unit Detail / board Status label → turnover columns (matches board Unit Info)."""
    key = (board_label or "").strip()
    if key == "Vacant ready":
        return {
            "manual_ready_status": MANUAL_READY_VACANT_READY,
            "availability_status": "vacant ready",
        }
    if key == "Vacant not ready":
        return {
            "manual_ready_status": MANUAL_READY_VACANT_NOT_READY,
            "availability_status": "vacant not ready",
        }
    if key == "On notice":
        return {
            "manual_ready_status": MANUAL_READY_ON_NOTICE,
            "availability_status": "on notice",
        }
    raise ValueError(f"Unknown status label: {board_label!r}")


def _autosave_turnover_after_attempt(turnover_id: int, **fields: object) -> None:
    """Call update_turnover; surface errors; clear cache.

    Used only from widget ``on_change`` callbacks — do not call ``st.rerun()`` here;
    Streamlit reruns the script after the callback, and rerun inside a callback is a no-op.
    """
    if not fields:
        return
    try:
        turnover_service.update_turnover(
            turnover_id,
            actor="manager",
            source="unit_detail_autosave",
            **fields,
        )
    except WritesDisabledError:
        st.warning("Database writes are currently disabled.")
    except turnover_service.TurnoverError as exc:
        st.error(str(exc))
    except (ValueError, TypeError) as exc:
        st.error(str(exc))
    except Exception as exc:  # noqa: BLE001
        st.error(f"Unexpected error: {exc}")
    st.cache_data.clear()


def _on_ud_status_autosave(turnover_id: int) -> None:
    """Status on_change: map label to fields, then shared turnover autosave."""
    try:
        fields = _unit_detail_status_to_fields(str(st.session_state.get("ud_status", "")))
    except ValueError as exc:
        st.error(str(exc))
        st.cache_data.clear()
        return
    _autosave_turnover_after_attempt(turnover_id, **fields)


def _on_legal_toggle_autosave(turnover_id: int) -> None:
    """Legal toggle on_change: persist both legal fields together (single update_turnover call)."""
    confirmed = bool(st.session_state.get("ud_legal"))
    if confirmed:
        _autosave_turnover_after_attempt(
            turnover_id,
            legal_confirmed_at=datetime.utcnow(),
            legal_confirmation_source="manual",
        )
    else:
        _autosave_turnover_after_attempt(
            turnover_id,
            legal_confirmed_at=None,
            legal_confirmation_source=None,
        )


def render_unit_detail() -> None:
    property_id = st.session_state.get("property_id")
    turnover_id = st.session_state.get("selected_turnover_id")

    # ── Lookup state (no turnover selected) ──────────────────────────────
    if turnover_id is None:
        _render_lookup(property_id)
        return

    data = unit_service.get_unit_detail(turnover_id)
    if data is None:
        st.error(f"Turnover {turnover_id} not found.")
        return

    detail = data["turnover"]
    unit = data["unit"]
    tasks = data["tasks"]
    readiness = data["readiness"]
    sla = data["sla"]
    dtbr = data["days_to_be_ready"]

    pid = detail["property_id"]
    phase = detail["lifecycle_phase"]
    phase_code, building_code = _resolve_structure(unit)
    unit_code = unit["unit_code_norm"] if unit else f"#{turnover_id}"
    dv = detail.get("days_since_move_out")
    ready_date = detail.get("report_ready_date")

    # ── Panel A: Unit Information ────────────────────────────────────────
    with st.container(border=True):
        st.markdown("**UNIT INFORMATION**")
        hdr_left, hdr_right = st.columns([4, 1])
        with hdr_left:
            legal_dot = "🟢" if detail.get("legal_confirmed_at") else "🔴"
            st.markdown(f"### Unit {unit_code} {legal_dot}")
        with hdr_right:
            if st.button("← Back", key="ud_back"):
                st.session_state.pop("selected_turnover_id", None)
                st.session_state.pop("board_info_editor", None)
                st.session_state.pop("board_task_editor", None)
                st.session_state.current_page = "board"
                st.rerun()

        st.toggle(
            "Legal confirmed",
            value=bool(detail.get("legal_confirmed_at")),
            key="ud_legal",
            on_change=lambda tid=turnover_id: _on_legal_toggle_autosave(tid),
        )

        id1, id2, id3, id4, id5 = st.columns([0.8, 0.8, 0.8, 0.8, 1.2])
        id1.write(f"**Phase:** {phase_code}")
        id2.write(f"**Building:** {building_code}")
        id3.write(f"**Unit:** {unit_code}")
        id4.write(f"**N/V/M:** {nvm_state(detail)}")
        id5.write(f"**Readiness:** {readiness_badge(readiness['state'])}")

    # ── Panel B: Status & QC ─────────────────────────────────────────────
    with st.container(border=True):
        s1, s2, s3 = st.columns([2, 1, 1])
        with s1:
            avail_status = detail.get("availability_status")
            current_status = avail_status.capitalize() if avail_status else status_label(phase)
            idx = _safe_index(STATUS_OPTIONS, current_status)
            st.selectbox(
                "Status",
                STATUS_OPTIONS,
                index=idx,
                key="ud_status",
                on_change=lambda tid=turnover_id: _on_ud_status_autosave(tid),
            )
        with s2:
            st.write("")
            st.markdown(f"**QC:** {qc_label(tasks)}")
        with s3:
            st.write("")
            st.markdown(f"**SLA:** {sla_indicator(sla.get('risk_level', 'OK'))}")

    # ── Panel C: Dates ───────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("**DATES**")
        dt1, dt2, dt3, dt4, dt5 = st.columns([1.2, 0.6, 1.2, 1.2, 0.6])
        with dt1:
            st.date_input(
                "Move-Out",
                value=detail.get("move_out_date"),
                key="ud_move_out",
                format="MM/DD/YYYY",
                on_change=lambda tid=turnover_id: _autosave_turnover_after_attempt(
                    tid,
                    move_out_date=st.session_state.get("ud_move_out"),
                ),
            )
        with dt2:
            dv_val = dv if dv is not None else 0
            if dv_val > 10:
                st.markdown("**DV**")
                st.markdown(f":red[**{dv_val}**]")
            else:
                st.metric("DV", dv_val)
        with dt3:
            st.date_input(
                "Ready Date",
                value=ready_date,
                key="ud_ready_date",
                format="MM/DD/YYYY",
                on_change=lambda tid=turnover_id: _autosave_turnover_after_attempt(
                    tid,
                    report_ready_date=st.session_state.get("ud_ready_date"),
                ),
            )
        with dt4:
            st.date_input(
                "Move-In",
                value=detail.get("move_in_date"),
                key="ud_move_in",
                format="MM/DD/YYYY",
                on_change=lambda tid=turnover_id: _autosave_turnover_after_attempt(
                    tid,
                    move_in_date=st.session_state.get("ud_move_in"),
                ),
            )
        dt5.metric("DTBR", dtbr if dtbr is not None else 0)

    # ── Panel D: W/D Status ──────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("**W/D STATUS**")
        w1, w2, w3 = st.columns(3)
        with w1:
            wd_expected = unit.get("has_wd_expected", False) if unit else False
            cur_wd = "Yes" if wd_expected else "No"
            st.selectbox(
                "Present", WD_OPTS,
                index=_safe_index(WD_OPTS, cur_wd),
                key="ud_wd_present",
            )
        with w2:
            st.write("")
            wd_notified_at = detail.get("wd_notified_at")
            if wd_notified_at is not None:
                st.markdown("**Notified:** ✅ Yes")
                st.caption(format_datetime(wd_notified_at))
                if st.button("Undo Notified", key="ud_wd_unnotify_btn"):
                    try:
                        turnover_service.undo_wd_notified(turnover_id, actor="manager")
                        st.cache_data.clear()
                        st.rerun()
                    except turnover_service.TurnoverError as e:
                        st.warning(str(e))
            else:
                st.markdown("**Notified:** No")
                if st.button("Mark Notified", key="ud_wd_notify_btn"):
                    turnover_service.mark_wd_notified(turnover_id, actor="manager")
                    st.cache_data.clear()
                    st.rerun()
        with w3:
            st.write("")
            wd_installed_at = detail.get("wd_installed_at")
            wd_notified_at = detail.get("wd_notified_at")
            if wd_installed_at is not None:
                st.markdown("**Installed:** ✅ Yes")
                st.caption(format_datetime(wd_installed_at))
                if st.button("Undo Installed", key="ud_wd_uninstall_btn"):
                    turnover_service.undo_wd_installed(turnover_id, actor="manager")
                    st.cache_data.clear()
                    st.rerun()
            else:
                st.markdown("**Installed:** No")
                install_disabled = wd_notified_at is None
                if st.button("Mark Installed", key="ud_wd_install_btn", disabled=install_disabled):
                    try:
                        turnover_service.mark_wd_installed(turnover_id, actor="manager")
                        st.cache_data.clear()
                        st.rerun()
                    except turnover_service.TurnoverError as e:
                        st.warning(str(e))
                if install_disabled:
                    st.caption(":orange[Mark notified first]")

    # ── Panel E: Risks ───────────────────────────────────────────────────
    risks = risk_service.get_open_risks(turnover_id)
    with st.container(border=True):
        st.markdown("**RISKS**")
        if risks:
            for r in risks:
                sev = r.get("severity", "")
                icon = "🔴" if sev == "CRITICAL" else "🟡" if sev == "WARNING" else "⚪"
                st.markdown(
                    f"{icon} {r.get('risk_type', '')} ({sev})"
                )
        else:
            st.caption("No active risks")

    # ── Panel E2: Authority & Import Comparison ──────────────────────────
    with st.expander("Authority & Import Comparison", expanded=False):
        _render_authority(detail)

    # ── Panel F: Tasks ───────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("**TASKS**")
        _render_tasks(tasks, pid, turnover_id, unit)

    # ── Panel G: Notes ───────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("**NOTES**")
        _render_notes(turnover_id, pid)

    # ── History (expander) ───────────────────────────────────────────────
    with st.expander("History", expanded=False):
        _render_audit(turnover_id)

    # ── Turnover Actions ─────────────────────────────────────────────────
    if data.get("is_open", False):
        with st.container(border=True):
            st.markdown("**TURNOVER ACTIONS**")
            if st.button("Cancel Turnover", key="ud_cancel_turnover"):
                try:
                    turnover_service.cancel_turnover(
                        turnover_id,
                        reason="Turnover cancelled by manager.",
                        actor="manager",
                    )
                    st.session_state.pop("selected_turnover_id", None)
                    st.session_state.pop("board_info_editor", None)
                    st.session_state.pop("board_task_editor", None)
                    st.session_state.current_page = "board"
                    st.rerun()
                except turnover_service.TurnoverError as e:
                    st.error(str(e))


# ── Lookup state ─────────────────────────────────────────────────────────────

def _render_lookup(property_id: int | None) -> None:
    st.caption("**Turnover Detail** — search for a unit to view its turnover")
    search = st.text_input(
        "Search unit", key="ud_unit_search",
        placeholder="e.g. A-101", label_visibility="collapsed",
    )
    if st.button("Go", key="ud_go") or (search and search != st.session_state.get("_ud_last_search")):
        st.session_state["_ud_last_search"] = search
        code = (search or "").strip()
        if not code or property_id is None:
            st.warning("Enter a valid unit code.")
            return
        unit = turnover_service.search_unit(property_id, code)
        if unit is None:
            st.warning(f"Unit **{code}** not found.")
            return
        turnover = turnover_service.get_open_turnover_for_unit(unit["unit_id"])
        if turnover is None:
            st.info(f"No open turnover for unit **{code}**.")
            return
        st.session_state.selected_turnover_id = turnover["turnover_id"]
        st.rerun()


# ── Tasks panel ──────────────────────────────────────────────────────────────

def _persist_task_update(tid: int, updates: dict) -> None:
    """Persist task updates immediately. Handles write guard. (Rerun happens automatically after callback.)"""
    try:
        task_service.update_task(tid, actor="manager", **updates)
        st.cache_data.clear()
    except WritesDisabledError:
        st.warning("Database writes are currently disabled.")


def _on_exec_change(tid: int) -> None:
    """Read execution widget state and persist execution_status + side effects."""
    new_exec_label = st.session_state.get(f"ud_exec_{tid}")
    new_exec = EXEC_REV.get(new_exec_label) if new_exec_label else None
    if not new_exec:
        return
    updates = {"execution_status": new_exec}
    updates.update(EXEC_SIDE_EFFECTS.get(new_exec_label) or {})
    _persist_task_update(tid, updates)


def _render_tasks(
    tasks: list[dict], property_id: int, turnover_id: int,
    unit: dict | None,
) -> None:
    if not tasks:
        st.caption("No tasks for this turnover.")
        return

    # Sort tasks by pipeline order
    _order = {code: i for i, code in enumerate(TASK_PIPELINE_ORDER)}
    tasks = sorted(tasks, key=lambda tk: _order.get(tk["task_type"], len(_order)))

    # Seed carpet status from unit on first render
    if "ud_carpet_status" not in st.session_state:
        has_carpet = unit.get("has_carpet", False) if unit else False
        st.session_state.ud_carpet_status = "Carpet" if has_carpet else "No Carpet"

    # Header: Task | Assignee | Date | Execution | Completed At | Req | Blocking
    th = st.columns([1.0, 1.2, 1.0, 1.2, 1.2, 0.5, 1.2])
    th[0].markdown("**Task**")
    th[1].markdown("**Assignee**")
    th[2].markdown("**Date**")
    th[3].markdown("**Execution**")
    th[4].markdown("**Completed At**")
    th[5].markdown("**Req**")
    th[6].markdown("**Blocking**")
    st.divider()

    for task in tasks:
        tid = task["task_id"]
        tt = task["task_type"]
        display_name = TASK_DISPLAY.get(tt, tt)

        exec_cur = EXEC_MAP.get(task["execution_status"], "Not Started")
        cur_assignee = task.get("assignee") or ""
        cur_blocking = "Not Blocking" if not task.get("blocking") else "—"
        completed_at_display = format_completed_date(task.get("completed_date"))

        tc = st.columns([1.0, 1.2, 1.0, 1.2, 1.2, 0.5, 1.2])

        with tc[0]:
            st.write(display_name)
            if tt == "CARPET":
                carpet_st = st.session_state.ud_carpet_status
                icon = CARPET_ICONS.get(carpet_st, "")
                if st.button(
                    f"{icon} {carpet_st}",
                    key="ud_carpet_cycle",
                    width="stretch",
                ):
                    idx = CARPET_STATUSES.index(carpet_st)
                    st.session_state.ud_carpet_status = CARPET_STATUSES[
                        (idx + 1) % len(CARPET_STATUSES)
                    ]
                    st.rerun()

        with tc[1]:
            st.text_input(
                "Assignee",
                value=cur_assignee,
                key=f"ud_assignee_{tid}",
                label_visibility="collapsed",
                on_change=lambda tid=tid: _persist_task_update(
                    tid,
                    {"assignee": (st.session_state.get(f"ud_assignee_{tid}", "") or "").strip() or None},
                ),
            )
        with tc[2]:
            st.date_input(
                "Date",
                value=task.get("vendor_due_date"),
                key=f"ud_due_{tid}",
                label_visibility="collapsed",
                format="MM/DD/YYYY",
                on_change=lambda tid=tid: _persist_task_update(
                    tid,
                    {"vendor_due_date": st.session_state.get(f"ud_due_{tid}")},
                ),
            )
        with tc[3]:
            st.selectbox(
                "Exec",
                EXEC_LABELS_EXTENDED,
                index=_safe_index(EXEC_LABELS_EXTENDED, exec_cur),
                key=f"ud_exec_{tid}",
                label_visibility="collapsed",
                on_change=lambda tid=tid: _on_exec_change(tid),
            )
        with tc[4]:
            st.text_input(
                "Completed At",
                value=completed_at_display,
                disabled=True,
                key=f"ud_completed_at_{tid}",
                label_visibility="collapsed",
            )
        with tc[5]:
            st.checkbox(
                "Req",
                value=bool(task.get("required")),
                key=f"ud_req_{tid}",
                label_visibility="collapsed",
                on_change=lambda tid=tid: _persist_task_update(
                    tid,
                    {"required": st.session_state.get(f"ud_req_{tid}", False)},
                ),
            )
        with tc[6]:
            st.selectbox(
                "Block",
                BLOCK_OPTIONS,
                index=_safe_index(BLOCK_OPTIONS, cur_blocking),
                key=f"ud_block_{tid}",
                label_visibility="collapsed",
                on_change=lambda tid=tid: _persist_task_update(
                    tid,
                    {"blocking": st.session_state.get(f"ud_block_{tid}") != "Not Blocking"},
                ),
            )


# ── Notes panel ──────────────────────────────────────────────────────────────

def _render_notes(turnover_id: int, property_id: int) -> None:
    notes = note_service.get_notes(turnover_id)
    if notes:
        for note in notes:
            icon = SEVERITY_ICONS.get(note.get("severity", ""), "")
            c1, c2 = st.columns([4, 1])
            c1.write(f"{icon} {note.get('text', '')} ({note.get('severity', 'INFO')})")
            with c2:
                if note.get("resolved_at") is None:
                    if st.button("Resolve", key=f"ud_note_resolve_{note['note_id']}"):
                        note_service.resolve_note(note["note_id"], actor="manager")
                        st.rerun()
                else:
                    st.caption("Resolved")
    else:
        st.caption("No notes yet.")

    st.text_area("Add note", key="ud_new_note", placeholder="Description…")
    nc1, nc2 = st.columns([1, 3])
    with nc1:
        severity = st.selectbox("Severity", NOTE_SEVERITIES, key="ud_note_sev")
    with nc2:
        st.write("")
        if st.button("Add note", key="ud_add_note"):
            text = st.session_state.get("ud_new_note", "").strip()
            if text:
                try:
                    note_service.add_note(property_id, turnover_id, severity, text, actor="manager")
                    st.rerun()
                except WritesDisabledError:
                    st.warning("Database writes are currently disabled.")


# ── Authority & Import Comparison ────────────────────────────────────────────

def _render_authority(detail: dict) -> None:
    avail_status = detail.get("availability_status")
    current_status = avail_status.capitalize() if avail_status else status_label(detail.get("lifecycle_phase", ""))
    legal_src = detail.get("legal_confirmation_source") or "—"
    auth_rows = [
        ("Move-Out Date", format_date(detail.get("move_out_date")),
         "Legal Confirmed" if detail.get("legal_confirmed_at") else "Import"),
        ("Move-In Date", format_date(detail.get("move_in_date")), "Import"),
        ("Status", current_status, "Import" if avail_status else "System"),
        ("Legal Confirmed",
         "Yes" if detail.get("legal_confirmed_at") else "No",
         legal_src),
    ]

    cols = st.columns([1.5, 1.5, 1])
    cols[0].markdown("**Field**")
    cols[1].markdown("**Current (System)**")
    cols[2].markdown("**Source**")
    for field, value, source in auth_rows:
        c0, c1, c2 = st.columns([1.5, 1.5, 1])
        c0.write(field)
        c1.write(value)
        c2.write(source)


# ── Audit timeline ───────────────────────────────────────────────────────────

def _render_audit(turnover_id: int) -> None:
    entries = audit_service.get_turnover_history(turnover_id)
    if not entries:
        st.caption("No history recorded.")
        return

    rows = [
        {
            "Date": format_date(e.get("changed_at")),
            "Field": e.get("field_name", ""),
            "From": e.get("old_value") or "—",
            "To": e.get("new_value") or "—",
            "By": e.get("actor", "system"),
            "Source": e.get("source", "—"),
        }
        for e in entries
    ]
    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_unit(unit_id: int | None) -> dict | None:
    if unit_id is None:
        return None
    return unit_service.get_unit_by_id(unit_id)


def _resolve_structure(unit: dict | None) -> tuple[str, str]:
    if unit is None:
        return "—", "—"
    phase_id = unit.get("phase_id")
    building_id = unit.get("building_id")
    phase_code = "—"
    building_code = "—"
    if phase_id is not None:
        phases = property_service.get_phases(unit.get("property_id", 0))
        for p in phases:
            if p["phase_id"] == phase_id:
                phase_code = p.get("phase_code", str(phase_id))
                if building_id is not None:
                    buildings = property_service.get_buildings(phase_id)
                    for b in buildings:
                        if b["building_id"] == building_id:
                            building_code = b.get("building_code", str(building_id))
                            break
                break
    return phase_code, building_code


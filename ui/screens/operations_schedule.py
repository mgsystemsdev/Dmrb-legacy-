"""Operations Schedule — schedule view over existing task data."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from services import scope_service, task_service
from services.write_guard import WritesDisabledError
from ui.helpers.formatting import format_date
from ui.state.constants import (
    EXEC_MAP,
    EXEC_REV,
    EXEC_LABELS,
    TASK_DISPLAY,
    TASK_PIPELINE_ORDER,
)


def render_operations_schedule() -> None:
    st.title("📅 Operations Schedule")

    property_id = st.session_state.get("property_id")
    if property_id is None:
        st.info("Select a property to view the schedule.")
        return

    phase_scope = scope_service.get_phase_scope(property_id)
    rows = task_service.get_schedule_rows(property_id, phase_scope=phase_scope)
    if not rows:
        st.info("No open tasks for the active property.")
        return

    # Sort by pipeline order, then by date
    order = {t: i for i, t in enumerate(TASK_PIPELINE_ORDER)}
    rows.sort(key=lambda r: (
        order.get(r["task_type"], len(order)),
        r.get("vendor_due_date") or date.max,
    ))

    tab_manager, tab_vendor = st.tabs(["Manager View", "Vendor View"])

    with tab_manager:
        _render_manager_view(property_id, rows)

    with tab_vendor:
        _render_vendor_view(rows)


# ── Manager View ─────────────────────────────────────────────────────────────

def _render_manager_view(property_id: int, rows: list[dict]) -> None:
    st.caption("Edit date, assignee, or status inline, then click **Save Changes**.")

    # Task type filter
    all_types = sorted({r["task_type"] for r in rows})
    type_labels = [TASK_DISPLAY.get(t, t) for t in all_types]
    selected_labels = st.multiselect(
        "Filter by task type",
        options=type_labels,
        default=type_labels,
        key="os_type_filter",
    )
    label_to_code = {TASK_DISPLAY.get(t, t): t for t in all_types}
    selected_codes = {label_to_code[lbl] for lbl in selected_labels}
    filtered = [r for r in rows if r["task_type"] in selected_codes]

    if not filtered:
        st.info("No tasks match the selected filters.")
        return

    df = pd.DataFrame([
        {
            "task_id": r["task_id"],
            "Task": TASK_DISPLAY.get(r["task_type"], r["task_type"]),
            "Unit": r["unit_code"],
            "Date": r.get("vendor_due_date"),
            "Assignee": r.get("assignee") or "",
            "Status": EXEC_MAP.get(r["execution_status"], r["execution_status"]),
        }
        for r in filtered
    ])

    edited = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=["task_id", "Task", "Unit"],
        column_config={
            "task_id": None,
            "Task": st.column_config.TextColumn("Task"),
            "Unit": st.column_config.TextColumn("Unit"),
            "Date": st.column_config.DateColumn("Date", format="MM/DD/YYYY"),
            "Assignee": st.column_config.TextColumn("Assignee"),
            "Status": st.column_config.SelectboxColumn(
                "Status", options=EXEC_LABELS,
            ),
        },
        key="os_manager_editor",
    )

    if st.button("Save Changes", key="os_save"):
        _save_schedule_changes(filtered, edited)


def _save_schedule_changes(rows: list[dict], edited: pd.DataFrame) -> None:
    changed = 0
    for idx, row_data in edited.iterrows():
        if idx >= len(rows):
            break
        original = rows[idx]
        updates: dict = {}

        # Date
        new_date = row_data.get("Date")
        if isinstance(new_date, pd.Timestamp):
            new_date = new_date.date()
        if new_date != original.get("vendor_due_date"):
            updates["vendor_due_date"] = new_date

        # Assignee
        new_assignee = (row_data.get("Assignee") or "").strip() or None
        if new_assignee != (original.get("assignee") or None):
            updates["assignee"] = new_assignee

        # Status
        new_status_label = row_data.get("Status")
        new_status = EXEC_REV.get(new_status_label)
        if new_status and new_status != original["execution_status"]:
            updates["execution_status"] = new_status

        if updates:
            try:
                task_service.update_task(
                    original["task_id"], actor="manager", **updates,
                )
                changed += 1
            except (task_service.TaskError, WritesDisabledError) as exc:
                st.error(f"Task {original['task_id']}: {exc}")

    if changed:
        st.success(f"Updated {changed} task(s).")
        st.cache_data.clear()
        st.rerun()
    else:
        st.info("No changes detected.")


# ── Vendor View ──────────────────────────────────────────────────────────────

def _render_vendor_view(rows: list[dict]) -> None:
    st.caption("Clean schedule view for vendor coordination.")

    df = pd.DataFrame([
        {
            "Date": format_date(r.get("vendor_due_date")),
            "Unit": r["unit_code"],
            "Task": TASK_DISPLAY.get(r["task_type"], r["task_type"]),
            "Assignee": r.get("assignee") or "—",
            "Status": EXEC_MAP.get(r["execution_status"], r["execution_status"]),
        }
        for r in rows
    ])

    st.dataframe(df, use_container_width=True, hide_index=True)

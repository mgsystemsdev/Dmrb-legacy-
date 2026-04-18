"""Board table component — Unit Info and Unit Tasks tabs using st.data_editor."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

import pandas as pd
import streamlit as st

from domain.availability_status import (
    MANUAL_READY_ON_NOTICE,
    MANUAL_READY_VACANT_NOT_READY,
    MANUAL_READY_VACANT_READY,
)
from services import task_service, turnover_service
from services.task_service import TaskError
from services.turnover_service import TurnoverError
from services.write_guard import WritesDisabledError
from ui.helpers.formatting import (
    board_breach_row_display,
    display_status_for_board_item,
    nvm_state,
    qc_label,
)
from ui.state.constants import (
    EXEC_MAP,
    EXEC_LABELS,
    EXEC_REV,
    STATUS_OPTIONS,
    TASK_COLS,
)

_QC_COLUMN_OPTIONS = ["QC Not Done", "QC Done", "Pending", "Confirmed"]


def _task_id_lookup(board: list[dict]) -> dict[tuple[int, str], int]:
    """Map (turnover_id, task_type) -> task_id."""
    out: dict[tuple[int, str], int] = {}
    for item in board:
        tid = item["turnover"]["turnover_id"]
        for t in item.get("tasks", []):
            out[(tid, t["task_type"])] = t["task_id"]
    return out


def _tasks_for_turnover(board: list[dict], turnover_id: int) -> list[dict]:
    for item in board:
        if item["turnover"]["turnover_id"] == turnover_id:
            return list(item.get("tasks", []))
    return []


def _board_any_turnover_missing_qc_task(board: list[dict]) -> bool:
    """True if any row on the board has no QUALITY_CONTROL task (QC column cannot be edited)."""
    for item in board:
        tasks = item.get("tasks", [])
        if not any(t.get("task_type") == "QUALITY_CONTROL" for t in tasks):
            return True
    return False


def _board_status_to_db(board_label: str) -> dict:
    """Map board Status dropdown -> turnover columns."""
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
    raise ValueError(f"Unknown board status label: {board_label!r}")


def _qc_label_to_execution_status(qc_ui: str) -> str:
    """Map board QC column value -> task execution_status."""
    q = (qc_ui or "").strip()
    if q in ("QC Done", "Confirmed"):
        return "COMPLETED"
    if q in ("QC Not Done", "Pending"):
        return "NOT_STARTED"
    raise ValueError(f"Unknown QC label: {qc_ui!r}")


def _apply_turnover_field_updates(
    turnover_id: int,
    field_to_value: dict[str, object],
    board: list[dict],
) -> None:
    """Merge logical board fields into one update_turnover call."""
    tasks = _tasks_for_turnover(board, turnover_id)
    payload: dict[str, object] = {}

    for fname, new_val in field_to_value.items():
        if fname == "status":
            payload.update(_board_status_to_db(str(new_val)))
        elif fname == "qc_status":
            qc_tasks = [t for t in tasks if t.get("task_type") == "QUALITY_CONTROL"]
            if not qc_tasks:
                raise TurnoverError(
                    f"Turnover {turnover_id} has no QUALITY_CONTROL task; "
                    "cannot update QC from the board."
                )
            exec_st = _qc_label_to_execution_status(str(new_val))
            task_service.update_task(
                int(qc_tasks[0]["task_id"]),
                actor="board",
                execution_status=exec_st,
            )
        elif fname == "ready_date":
            payload["report_ready_date"] = new_val
        elif fname in ("move_out_date", "move_in_date"):
            payload[fname] = new_val
        else:
            raise ValueError(f"Unsupported turnover field for board save: {fname!r}")

    if payload:
        turnover_service.update_turnover(
            turnover_id,
            actor="board",
            source="board_inline_edit",
            **payload,
        )


def _apply_info_tab_mutations(mutations: list[dict], board: list[dict]) -> bool:
    """Persist Unit Info mutations. Returns True if at least one turnover save succeeded."""
    if not mutations:
        return False

    by_turnover: dict[int, dict[str, object]] = defaultdict(dict)
    for m in mutations:
        if m.get("entity") != "turnover":
            continue
        tid = int(m["turnover_id"])
        field = str(m["field"])
        by_turnover[tid][field] = m["new"]

    any_success = False
    for tid, fmap in by_turnover.items():
        qc_only = set(fmap.keys()) <= {"qc_status"}
        try:
            if qc_only:
                _apply_turnover_field_updates(tid, fmap, board)
                any_success = True
            else:
                qc = fmap.pop("qc_status", None)
                if fmap:
                    _apply_turnover_field_updates(tid, dict(fmap), board)
                    any_success = True
                if qc is not None:
                    _apply_turnover_field_updates(tid, {"qc_status": qc}, board)
                    any_success = True
        except (TurnoverError, TaskError, ValueError, WritesDisabledError) as exc:
            st.error(f"Turnover {tid}: {exc}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Turnover {tid}: unexpected error: {exc}")

    return any_success


def _apply_task_tab_mutations(
    mutations: list[dict],
    lookup: dict[tuple[int, str], int],
) -> bool:
    """Persist Unit Tasks mutations. Returns True if at least one task save succeeded."""
    if not mutations:
        return False

    by_task: dict[int, dict[str, object]] = defaultdict(dict)
    resolve_errors: list[str] = []

    for m in mutations:
        if m.get("entity") != "task":
            continue
        tid = int(m["turnover_id"])
        ttype = str(m["task_type"])
        key = (tid, ttype)
        task_id = lookup.get(key)
        if task_id is None:
            resolve_errors.append(f"Turnover {tid}: no task row for type {ttype!r}.")
            continue
        field = m["field"]
        new_val = m["new"]
        if field == "status":
            exec_st = new_val if new_val is not None else "NOT_STARTED"
            by_task[task_id]["execution_status"] = exec_st
        elif field == "due_date":
            by_task[task_id]["vendor_due_date"] = new_val
        else:
            resolve_errors.append(f"Task {task_id}: unknown field {field!r}.")

    for msg in resolve_errors:
        st.error(msg)

    any_success = False
    for task_id, fields in by_task.items():
        if not fields:
            continue
        try:
            task_service.update_task(task_id, actor="board", **fields)
            any_success = True
        except (TaskError, WritesDisabledError) as exc:
            st.error(f"Task {task_id}: {exc}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Task {task_id}: unexpected error: {exc}")

    return any_success


def render_board_tabs(board: list[dict]) -> None:
    """Render the Unit Info / Unit Tasks tabs for the board."""
    if not board:
        st.info("No turnovers to display.")
        return

    # Collect all task types present in the board
    task_types_seen: list[str] = []
    for item in board:
        for t in item.get("tasks", []):
            if t["task_type"] not in task_types_seen:
                task_types_seen.append(t["task_type"])
    # Use canonical order, then any extras
    task_cols = [tc for tc in TASK_COLS if tc in task_types_seen]
    for tt in task_types_seen:
        if tt not in task_cols:
            task_cols.append(tt)

    info_data, task_data, tid_list = _build_dataframes(board, task_cols)

    df_info = pd.DataFrame(info_data)
    df_task = pd.DataFrame(task_data)
    lookup = _task_id_lookup(board)

    tab_info, tab_tasks = st.tabs(["Unit Info", "Unit Tasks"])

    with tab_info:
        _render_info_tab(df_info, tid_list, board)

    with tab_tasks:
        _render_tasks_tab(df_task, task_cols, tid_list, lookup)


def _build_dataframes(
    board: list[dict], task_cols: list[str],
) -> tuple[list[dict], list[dict], list[int]]:
    """Build row dicts for both tabs from board items."""
    info_rows: list[dict] = []
    task_rows: list[dict] = []
    tid_list: list[int] = []

    for item in board:
        turnover = item["turnover"]
        unit = item.get("unit")
        tasks = item.get("tasks", [])
        tid = turnover["turnover_id"]
        tid_list.append(tid)

        unit_code = unit["unit_code_norm"] if unit else "—"
        dv = turnover.get("days_since_move_out")
        dtbr = turnover.get("days_to_be_ready")

        move_out = turnover.get("move_out_date")
        move_in = turnover.get("move_in_date")
        ready_date = turnover.get("report_ready_date")

        # Status: use effective status for display (avoids showing Vacant Not Ready for Vacant Ready units)
        display_status = display_status_for_board_item(item)

        # W/D summary
        wd = "Yes" if unit and unit.get("has_wd_expected") else "—"

        # Notes summary (first open note text, truncated)
        notes_list = item.get("notes", [])
        open_notes = [n for n in notes_list if n.get("resolved_at") is None]
        notes_summary = open_notes[0]["text"][:60] if open_notes else ""

        bd = board_breach_row_display(item)
        alert_display = bd.alert_display

        legal_confirmed = turnover.get("legal_confirmed_at") is not None
        legal_dot = "🟢" if legal_confirmed else "🔴"

        info_rows.append({
            "▶": False,
            "⚖": legal_dot,
            "Unit": unit_code,
            "Status": display_status,
            "Move-Out": move_out,
            "Ready Date": ready_date,
            "DV": dv if dv is not None else 0,
            "Move-In": move_in,
            "DTBR": dtbr if dtbr is not None else 0,
            "N/V/M": nvm_state(turnover),
            "W/D": wd,
            "QC": qc_label(tasks),
            "Alert": alert_display,
            "Notes": notes_summary,
        })

        # Task execution status per type
        task_by_type = {t["task_type"]: t for t in tasks}
        task_row: dict = {
            "▶": False,
            "Unit": unit_code,
            "⚖": legal_dot,
            "Status": display_status,
            "DV": dv if dv is not None else 0,
            "DTBR": dtbr if dtbr is not None else 0,
        }
        for tc in task_cols:
            t = task_by_type.get(tc)
            if t:
                task_row[tc] = _exec_display(t["execution_status"])
                task_row[f"{tc} Date"] = t.get("vendor_due_date")
            else:
                task_row[tc] = "—"
                task_row[f"{tc} Date"] = None

        task_rows.append(task_row)

    return info_rows, task_rows, tid_list


def _exec_display(status: str) -> str:
    return EXEC_MAP.get(status, status)


def _render_info_tab(df: pd.DataFrame, tid_list: list[int], board: list[dict]) -> None:
    col_config = {
        "▶": st.column_config.CheckboxColumn("▶", width=40),
        "⚖": st.column_config.TextColumn("⚖", width=35),
        "Unit": st.column_config.TextColumn("Unit"),
        "Status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS),
        "Move-Out": st.column_config.DateColumn("Move-Out", format="MM/DD/YYYY"),
        "Ready Date": st.column_config.DateColumn("Ready Date", format="MM/DD/YYYY"),
        "DV": st.column_config.NumberColumn("DV", width=50),
        "Move-In": st.column_config.DateColumn("Move-In", format="MM/DD/YYYY"),
        "DTBR": st.column_config.NumberColumn("DTBR", width=60),
        "N/V/M": st.column_config.TextColumn("N/V/M", width=80),
        "W/D": st.column_config.TextColumn("W/D", width=50),
        "QC": st.column_config.SelectboxColumn("QC", options=_QC_COLUMN_OPTIONS),
        "Alert": st.column_config.TextColumn("Alert", width=50),
        "Notes": st.column_config.TextColumn("Notes", width=140),
    }
    disabled_info = ["⚖", "Unit", "DV", "DTBR", "N/V/M", "W/D", "Alert", "Notes"]
    if _board_any_turnover_missing_qc_task(board):
        disabled_info.append("QC")
        st.caption(
            "QC is read-only here: at least one unit on this board has no QUALITY_CONTROL "
            "task. Add that task (templates or unit workflow) to edit QC from the board."
        )
    edited = st.data_editor(
        df,
        height=35 * len(df) + 40,
        column_config=col_config,
        hide_index=True,
        num_rows="fixed",
        use_container_width=True,
        key="board_info_editor",
        disabled=disabled_info,
    )

    _INFO_COL_TO_FIELD = {
        "Status": "status",
        "Move-Out": "move_out_date",
        "Ready Date": "ready_date",
        "Move-In": "move_in_date",
        "QC": "qc_status",
    }
    _diff_info_date_cols = frozenset({"Move-Out", "Ready Date", "Move-In"})

    def _norm_cell_info(val: object, *, is_date_column: bool) -> object:
        if val is None:
            return None
        if isinstance(val, str) and val.strip() == "":
            return None
        if isinstance(val, bool):
            return val
        try:
            if pd.isna(val):
                return None
        except TypeError:
            pass
        if is_date_column:
            ts = pd.to_datetime(val, errors="coerce")
            if pd.isna(ts):
                return None
            return pd.Timestamp(ts).normalize()
        if isinstance(val, pd.Timestamp):
            return val.normalize()
        if isinstance(val, datetime):
            return pd.Timestamp(val).normalize()
        if isinstance(val, date):
            return pd.Timestamp(val).normalize()
        return val

    def _info_value_for_mutation(col: str, raw: object) -> object:
        if col in _diff_info_date_cols:
            val = _norm_cell_info(raw, is_date_column=True)
            return None if val is None else pd.Timestamp(val).date()
        try:
            if raw is None or pd.isna(raw):
                return None
        except TypeError:
            if raw is None:
                return None
        if isinstance(raw, str) and raw.strip() == "":
            return None
        return str(raw).strip()

    mutations: list[dict] = []
    if len(df) == len(edited) == len(tid_list):
        for i in range(len(df)):
            turnover_id = tid_list[i]
            for col in _INFO_COL_TO_FIELD:
                if col not in df.columns or col not in edited.columns:
                    continue
                old_raw = df.iloc[i][col]
                new_raw = edited.iloc[i][col]
                old_val = _info_value_for_mutation(col, old_raw)
                new_val = _info_value_for_mutation(col, new_raw)
                if old_val != new_val:
                    mutations.append(
                        {
                            "turnover_id": turnover_id,
                            "entity": "turnover",
                            "field": _INFO_COL_TO_FIELD[col],
                            "old": old_val,
                            "new": new_val,
                        }
                    )
    if mutations:
        _apply_info_tab_mutations(mutations, board)
        st.session_state.pop("board_info_editor", None)
        st.cache_data.clear()
        st.rerun()

    # Handle row selection via ▶ checkbox
    _handle_row_select(edited, tid_list, "info")


def _render_tasks_tab(
    df: pd.DataFrame,
    task_cols: list[str],
    tid_list: list[int],
    lookup: dict[tuple[int, str], int],
) -> None:
    col_config: dict = {
        "▶": st.column_config.CheckboxColumn("▶", width=40),
        "Unit": st.column_config.TextColumn("Unit"),
        "⚖": st.column_config.TextColumn("⚖", width=35),
        "Status": st.column_config.TextColumn("Status"),
        "DV": st.column_config.NumberColumn("DV", width=50),
        "DTBR": st.column_config.NumberColumn("DTBR", width=60),
    }
    for tc in task_cols:
        col_config[tc] = st.column_config.SelectboxColumn(tc, options=EXEC_LABELS + ["—"])
        col_config[f"{tc} Date"] = st.column_config.DateColumn(
            f"{tc} Date", format="MM/DD/YYYY",
        )

    col_order = ["▶", "Unit", "⚖", "Status", "DV", "DTBR"]
    for tc in task_cols:
        col_order.extend([tc, f"{tc} Date"])

    disabled_cols = ["Unit", "⚖", "Status", "DV", "DTBR"]
    edited = st.data_editor(
        df,
        height=35 * len(df) + 40,
        column_config=col_config,
        column_order=col_order,
        hide_index=True,
        num_rows="fixed",
        use_container_width=True,
        key="board_task_editor",
        disabled=disabled_cols,
    )

    editable_columns: list[str] = []
    for _tc in task_cols:
        editable_columns.extend([_tc, f"{_tc} Date"])

    def _norm_cell_task(val: object, *, is_date_column: bool) -> object:
        if val is None:
            return None
        if isinstance(val, str) and val.strip() == "":
            return None
        if isinstance(val, bool):
            return val
        try:
            if pd.isna(val):
                return None
        except TypeError:
            pass
        if is_date_column:
            ts = pd.to_datetime(val, errors="coerce")
            if pd.isna(ts):
                return None
            return pd.Timestamp(ts).normalize()
        if isinstance(val, pd.Timestamp):
            return val.normalize()
        if isinstance(val, datetime):
            return pd.Timestamp(val).normalize()
        if isinstance(val, date):
            return pd.Timestamp(val).normalize()
        return val

    def _task_status_db(val: object) -> str | None:
        val = _norm_cell_task(val, is_date_column=False)
        if val is None:
            return None
        s = str(val).strip()
        if s in ("", "—"):
            return None
        return EXEC_REV.get(s)

    def _task_due_mutation(val: object) -> date | None:
        val = _norm_cell_task(val, is_date_column=True)
        return None if val is None else pd.Timestamp(val).date()

    mutations: list[dict] = []
    if len(df) == len(edited) == len(tid_list):
        for i in range(len(df)):
            turnover_id = tid_list[i]
            for col in editable_columns:
                if col == "▶":
                    continue
                if col not in df.columns or col not in edited.columns:
                    continue
                old_raw = df.iloc[i][col]
                new_raw = edited.iloc[i][col]
                if col.endswith(" Date"):
                    task_type = col.replace(" Date", "")
                    field = "due_date"
                    old_val = _task_due_mutation(old_raw)
                    new_val = _task_due_mutation(new_raw)
                else:
                    task_type = col
                    field = "status"
                    old_val = _task_status_db(old_raw)
                    new_val = _task_status_db(new_raw)
                if old_val != new_val:
                    mutations.append(
                        {
                            "turnover_id": turnover_id,
                            "entity": "task",
                            "task_type": task_type,
                            "field": field,
                            "old": old_val,
                            "new": new_val,
                        }
                    )
    if mutations:
        _apply_task_tab_mutations(mutations, lookup)
        st.cache_data.clear()
        st.rerun()

    _handle_row_select(edited, tid_list, "task")


def _handle_row_select(
    edited: pd.DataFrame, tid_list: list[int], tab: str,
) -> None:
    """Navigate to unit_detail when a ▶ checkbox is toggled on."""
    if "▶" not in edited.columns:
        return
    selected = edited[edited["▶"] == True]  # noqa: E712
    if not selected.empty:
        idx = selected.index[0]
        if idx < len(tid_list):
            st.session_state.selected_turnover_id = tid_list[idx]
            st.session_state.current_page = "unit_detail"
            st.rerun()

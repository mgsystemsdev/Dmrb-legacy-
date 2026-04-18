from __future__ import annotations
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from api.schemas.board import BoardResponse, BoardRow, BoardTask
from api.deps import get_current_user
from services import board_service
from ui.helpers.formatting import board_breach_row_display, display_status_for_board_item, nvm_label, qc_label

router = APIRouter()

@router.get("/board/{property_id}", response_model=BoardResponse)
async def get_property_board(
    property_id: int,
    phase: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    nvm: Optional[str] = Query(None),
    qc: Optional[str] = Query(None),
    board_filter: Optional[str] = Query(None),
    user: dict = Depends(get_current_user)
):
    today = date.today()
    # board_service.get_board_view handles phase_scope reconciliation
    items = board_service.get_board_view(property_id, today=today)

    if board_filter:
        items = board_service.filter_by_flag_category(items, board_filter)

    rows = []
    for item in items:
        turnover = item["turnover"]
        unit = item.get("unit") or {}
        readiness_data = item["readiness"]
        status_label = display_status_for_board_item(item)
        nvm_value = nvm_label(turnover["lifecycle_phase"])
        qc_value = qc_label(item.get("tasks", []))
        alert = board_breach_row_display(item).alert_display

        tasks: list[BoardTask] = []
        for task in item.get("tasks", []):
            tasks.append(
                BoardTask(
                    task_id=task["task_id"],
                    task_type=task["task_type"],
                    execution_status=task["execution_status"],
                    assignee=task.get("assignee"),
                    vendor_due_date=task.get("vendor_due_date"),
                    scheduled_date=task.get("scheduled_date"),
                    manager_confirmed_at=task.get("manager_confirmed_at").isoformat()
                    if task.get("manager_confirmed_at")
                    else None,
                )
            )

        row = BoardRow(
            turnover_id=turnover["turnover_id"],
            unit_id=unit.get("unit_id"),
            unit_code=unit.get("unit_code_norm", "?"),
            phase_id=unit.get("phase_id"),
            phase_code=unit.get("phase_code"),
            phase=unit.get("phase_name", "Unknown"),
            status=status_label,
            nvm=nvm_value,
            qc=qc_value,
            alert=alert,
            move_out_date=turnover.get("move_out_date"),
            report_ready_date=turnover.get("report_ready_date"),
            lifecycle_phase=turnover["lifecycle_phase"],
            readiness=readiness_data["state"],
            priority=item["priority"],
            days_since_move_out=turnover.get("days_since_move_out"),
            days_to_move_in=turnover.get("days_to_move_in"),
            days_to_be_ready=turnover.get("days_to_be_ready"),
            move_in_date=turnover.get("move_in_date"),
            notes_summary=(item.get("notes", [{}])[0].get("text", "")[:60] if item.get("notes") else ""),
            task_completion=(readiness_data["completed"], readiness_data["total"]),
            agreements=item["agreements"],
            tasks=tasks,
        )

        # Apply filters
        if search and search.lower() not in row.unit_code.lower():
            continue
        if phase and row.phase != phase and row.phase_code != phase:
            continue
        if status and row.status != status:
            continue
        if nvm and row.nvm != nvm:
            continue
        if qc and row.qc != qc:
            continue

        rows.append(row)

    task_types_seen: list[str] = []
    for row in rows:
        for task in row.tasks:
            if task.task_type not in task_types_seen:
                task_types_seen.append(task.task_type)

    return BoardResponse(
        property_id=property_id,
        as_of=today,
        rows=rows,
        task_types_present=task_types_seen,
        total=len(rows)
    )

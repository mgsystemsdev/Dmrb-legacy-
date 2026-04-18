from __future__ import annotations
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from api.schemas.board import BoardResponse, BoardRow
from api.deps import get_current_user
from services import board_service

router = APIRouter()

@router.get("/board/{property_id}", response_model=BoardResponse)
async def get_property_board(
    property_id: int,
    phase: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    readiness: Optional[str] = Query(None),
    user: dict = Depends(get_current_user)
):
    today = date.today()
    # board_service.get_board_view handles phase_scope reconciliation
    items = board_service.get_board_view(property_id, today=today)
    
    rows = []
    for item in items:
        # Extract fields for BoardRow
        turnover = item["turnover"]
        unit = item.get("unit") or {}
        readiness_data = item["readiness"]
        
        row = BoardRow(
            turnover_id=turnover["turnover_id"],
            unit_code=unit.get("unit_code_norm", "?"),
            phase=unit.get("phase_name", "Unknown"),
            lifecycle_phase=turnover["lifecycle_phase"],
            readiness=readiness_data["state"],
            priority=item["priority"],
            days_since_move_out=turnover.get("days_since_move_out"),
            days_to_move_in=turnover.get("days_to_move_in"),
            move_in_date=turnover.get("move_in_date"),
            task_completion=(readiness_data["completed"], readiness_data["total"]),
            agreements=item["agreements"]
        )
        
        # Apply filters
        if phase and row.phase != phase:
            continue
        if priority and row.priority != priority:
            continue
        if readiness and row.readiness != readiness:
            continue
            
        rows.append(row)
        
    return BoardResponse(
        property_id=property_id,
        as_of=today,
        rows=rows,
        total=len(rows)
    )

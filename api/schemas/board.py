from __future__ import annotations
from pydantic import BaseModel
from datetime import date
from typing import Dict, List, Optional, Tuple


class BoardTask(BaseModel):
    task_id: int
    task_type: str
    execution_status: str
    assignee: Optional[str] = None
    vendor_due_date: Optional[date] = None
    scheduled_date: Optional[date] = None
    manager_confirmed_at: Optional[str] = None


class BoardRow(BaseModel):
    turnover_id: int
    unit_id: Optional[int] = None
    unit_code: str
    phase_id: Optional[int] = None
    phase_code: Optional[str] = None
    phase: str
    status: str
    nvm: str
    qc: str
    alert: str
    move_out_date: Optional[date] = None
    report_ready_date: Optional[date] = None
    lifecycle_phase: str
    readiness: str
    priority: str
    days_since_move_out: Optional[int] = None
    days_to_move_in: Optional[int] = None
    days_to_be_ready: Optional[int] = None
    move_in_date: Optional[date] = None
    notes_summary: str = ""
    task_completion: Tuple[int, int]
    agreements: Dict[str, str]
    tasks: List[BoardTask]

class BoardResponse(BaseModel):
    property_id: int
    as_of: date
    rows: List[BoardRow]
    task_types_present: List[str]
    total: int

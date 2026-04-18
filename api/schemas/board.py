from __future__ import annotations
from pydantic import BaseModel
from datetime import date
from typing import Dict, List, Optional, Tuple

class BoardRow(BaseModel):
    turnover_id: int
    unit_code: str
    phase: str
    lifecycle_phase: str
    readiness: str
    priority: str
    days_since_move_out: Optional[int] = None
    days_to_move_in: Optional[int] = None
    move_in_date: Optional[date] = None
    task_completion: Tuple[int, int]
    agreements: Dict[str, str]

class BoardResponse(BaseModel):
    property_id: int
    as_of: date
    rows: List[BoardRow]
    total: int

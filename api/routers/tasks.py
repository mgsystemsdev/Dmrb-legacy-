from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_current_user
from db.repository import task_repository
from services import task_service
from services.task_service import TaskError

router = APIRouter()


class PatchTaskRequest(BaseModel):
    execution_status: Optional[str] = None
    assignee: Optional[str] = None
    vendor_due_date: Optional[date] = None
    scheduled_date: Optional[date] = None
    required: Optional[bool] = None
    blocking: Optional[bool] = None


def _serialize(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, date):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


@router.get("/turnovers/{turnover_id}/tasks")
async def get_tasks(turnover_id: int, user: dict = Depends(get_current_user)):
    tasks = task_repository.get_by_turnover(turnover_id)
    return [_serialize(t) for t in tasks]


@router.patch("/turnovers/{turnover_id}/tasks/{task_id}")
async def patch_task(
    turnover_id: int,
    task_id: int,
    body: PatchTaskRequest,
    user: dict = Depends(get_current_user),
):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        updated = task_service.update_task(task_id, actor=user.get("username", "api"), **fields)
        return _serialize(updated)
    except TaskError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

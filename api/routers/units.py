from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_current_user
from db.repository import unit_repository
from services.write_guard import check_writes_enabled

router = APIRouter()


class PatchUnitRequest(BaseModel):
    field: str
    value: Any


@router.patch("/units/{unit_id}")
async def patch_unit(
    unit_id: int,
    body: PatchUnitRequest,
    user: dict = Depends(get_current_user),
):
    allowed_fields = {"has_wd_expected"}
    if body.field not in allowed_fields:
        raise HTTPException(status_code=400, detail=f"Field '{body.field}' is not patchable")

    check_writes_enabled()
    updated = unit_repository.update(unit_id, **{body.field: body.value})
    if updated is None:
        raise HTTPException(status_code=404, detail="Unit not found")
    return updated

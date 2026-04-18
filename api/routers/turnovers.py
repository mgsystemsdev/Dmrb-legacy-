from __future__ import annotations
from datetime import date, datetime
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.deps import get_current_user
from services import turnover_service, audit_service, risk_service, unit_service
from services.turnover_service import TurnoverError
from domain.availability_status import (
    MANUAL_READY_ON_NOTICE,
    MANUAL_READY_VACANT_NOT_READY,
    MANUAL_READY_VACANT_READY,
)
from api.presentation.formatting import status_label

router = APIRouter()


class CreateTurnoverRequest(BaseModel):
    unit_id: int
    move_out_date: date
    move_in_date: Optional[date] = None


class PatchTurnoverRequest(BaseModel):
    field: str
    value: Any


class CancelTurnoverRequest(BaseModel):
    reason: str


def _serialize(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, date):
            out[k] = v.isoformat()
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _serialize_any(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _serialize_any(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_any(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _status_payload(status_label: str) -> dict[str, str]:
    normalized = (status_label or "").strip()
    if normalized == "Vacant ready":
        return {
            "manual_ready_status": MANUAL_READY_VACANT_READY,
            "availability_status": "vacant ready",
        }
    if normalized == "Vacant not ready":
        return {
            "manual_ready_status": MANUAL_READY_VACANT_NOT_READY,
            "availability_status": "vacant not ready",
        }
    if normalized == "On notice":
        return {
            "manual_ready_status": MANUAL_READY_ON_NOTICE,
            "availability_status": "on notice",
        }
    raise TurnoverError(f"Unsupported board status '{status_label}'")


@router.get("/turnovers/{turnover_id}")
async def get_turnover(turnover_id: int, user: dict = Depends(get_current_user)):
    detail = turnover_service.get_turnover_detail(turnover_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Turnover not found")
    return _serialize(detail)


@router.get("/turnovers/{turnover_id}/detail")
async def get_turnover_detail(turnover_id: int, user: dict = Depends(get_current_user)):
    detail = unit_service.get_unit_detail(turnover_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Turnover not found")
    detail["risks"] = risk_service.get_open_risks(turnover_id)
    return _serialize_any(detail)


@router.get("/turnovers/{turnover_id}/authority")
async def get_turnover_authority(turnover_id: int, user: dict = Depends(get_current_user)):
    detail = turnover_service.get_turnover_detail(turnover_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Turnover not found")

    avail_status = detail.get("availability_status")
    if avail_status:
        normalized = str(avail_status).strip().lower()
        current_status = {
            "on notice": "On notice",
            "on notice (break)": "On notice",
            "vacant not ready": "Vacant not ready",
            "vacant ready": "Vacant ready",
        }.get(normalized, str(avail_status))
    else:
        current_status = status_label(str(detail.get("lifecycle_phase", "")))
    legal_src = detail.get("legal_confirmation_source") or "—"
    rows = [
        {
            "field": "Move-Out Date",
            "current_value": _serialize_any(detail.get("move_out_date")) or "—",
            "source": "Legal Confirmed" if detail.get("legal_confirmed_at") else "Import",
        },
        {
            "field": "Move-In Date",
            "current_value": _serialize_any(detail.get("move_in_date")) or "—",
            "source": "Import",
        },
        {
            "field": "Status",
            "current_value": current_status,
            "source": "Import" if avail_status else "System",
        },
        {
            "field": "Legal Confirmed",
            "current_value": "Yes" if detail.get("legal_confirmed_at") else "No",
            "source": legal_src,
        },
    ]
    return {"rows": rows}


@router.post("/turnovers")
async def create_turnover(
    body: CreateTurnoverRequest,
    property_id: int,
    user: dict = Depends(get_current_user),
):
    try:
        t = turnover_service.create_turnover(
            property_id,
            body.unit_id,
            body.move_out_date,
            move_in_date=body.move_in_date,
            actor=user.get("username", "api"),
        )
        return _serialize(t)
    except TurnoverError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/turnovers/{turnover_id}")
async def patch_turnover(
    turnover_id: int,
    body: PatchTurnoverRequest,
    user: dict = Depends(get_current_user),
):
    allowed_fields = {
        "move_out_date", "move_in_date", "report_ready_date",
        "availability_status", "manual_ready_status",
        "legal_hold", "notes_to_self",
        "wd_present", "wd_notified_at", "wd_installed_at",
        "status",
    }
    if body.field not in allowed_fields:
        raise HTTPException(status_code=400, detail=f"Field '{body.field}' is not patchable")
    try:
        if body.field == "status":
            payload = _status_payload(str(body.value))
        else:
            payload = {body.field: body.value}
        updated = turnover_service.update_turnover(
            turnover_id,
            actor=user.get("username", "api"),
            source="api",
            **payload,
        )
        return _serialize(updated)
    except TurnoverError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/turnovers/{turnover_id}")
async def cancel_turnover(
    turnover_id: int,
    body: CancelTurnoverRequest,
    user: dict = Depends(get_current_user),
):
    try:
        updated = turnover_service.cancel_turnover(
            turnover_id,
            body.reason,
            actor=user.get("username", "api"),
        )
        return _serialize(updated)
    except TurnoverError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/turnovers/{turnover_id}/audit")
async def get_turnover_audit(turnover_id: int, user: dict = Depends(get_current_user)):
    rows = audit_service.get_turnover_history(turnover_id)
    return [_serialize(r) for r in rows]


# W/D workflow actions
@router.post("/turnovers/{turnover_id}/wd/notify")
async def wd_notify(turnover_id: int, user: dict = Depends(get_current_user)):
    try:
        return _serialize(turnover_service.mark_wd_notified(turnover_id, actor=user.get("username", "api")))
    except TurnoverError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/turnovers/{turnover_id}/wd/install")
async def wd_install(turnover_id: int, user: dict = Depends(get_current_user)):
    try:
        return _serialize(turnover_service.mark_wd_installed(turnover_id, actor=user.get("username", "api")))
    except TurnoverError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/turnovers/{turnover_id}/wd/notify")
async def wd_undo_notify(turnover_id: int, user: dict = Depends(get_current_user)):
    try:
        return _serialize(turnover_service.undo_wd_notified(turnover_id, actor=user.get("username", "api")))
    except TurnoverError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/turnovers/{turnover_id}/wd/install")
async def wd_undo_install(turnover_id: int, user: dict = Depends(get_current_user)):
    try:
        return _serialize(turnover_service.undo_wd_installed(turnover_id, actor=user.get("username", "api")))
    except TurnoverError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

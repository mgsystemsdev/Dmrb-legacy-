from __future__ import annotations

import logging
from datetime import date, datetime
from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.deps import get_current_user
from services import property_service, unit_service
from services.unit_service import UnitMasterImportError
from services.write_guard import WritesDisabledError, check_writes_enabled

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/unit-master", tags=["unit-master"])


class UnitMasterResponse(BaseModel):
    success: bool
    data: Any = None
    errors: list[str] = Field(default_factory=list)


class CreateUnitBody(BaseModel):
    unit_code: str
    phase_id: int | None = None
    building_id: int | None = None
    floor_plan: str | None = None
    gross_sq_ft: int | None = None
    has_carpet: bool = False
    has_wd_expected: bool = False


def _serialize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _fail(status_code: int, errors: list[str]) -> JSONResponse:
    body = UnitMasterResponse(success=False, data=None, errors=errors).model_dump()
    return JSONResponse(status_code=status_code, content=body)


def _ok(data: Any = None, errors: list[str] | None = None) -> dict[str, Any]:
    return UnitMasterResponse(
        success=True,
        data=data,
        errors=errors or [],
    ).model_dump()


def _validate_property_id(property_id: int) -> JSONResponse | None:
    if property_id < 1:
        return _fail(400, ["property_id must be a positive integer"])
    if property_service.get_property_by_id(property_id) is None:
        return _fail(404, [f"Property {property_id} not found"])
    return None


def _validate_create_placement(
    property_id: int,
    phase_id: int | None,
    building_id: int | None,
) -> tuple[int | None, JSONResponse | None]:
    resolved_phase_id = phase_id
    if building_id is not None:
        b = property_service.get_building_by_id(building_id)
        if b is None:
            return None, _fail(400, [f"Building {building_id} not found"])
        if int(b["property_id"]) != property_id:
            return None, _fail(400, ["building_id does not belong to this property"])
        b_phase = int(b["phase_id"])
        if resolved_phase_id is not None and resolved_phase_id != b_phase:
            return None, _fail(400, ["phase_id does not match building's phase"])
        resolved_phase_id = b_phase
    if resolved_phase_id is not None:
        ph = property_service.get_phase_by_id(resolved_phase_id)
        if ph is None:
            return None, _fail(400, [f"Phase {resolved_phase_id} not found"])
        if int(ph["property_id"]) != property_id:
            return None, _fail(400, ["phase_id does not belong to this property"])
    return resolved_phase_id, None


@router.post("/import")
async def import_unit_master_csv(
    property_id: int = Form(...),
    strict: bool = Form(False),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    prop_err = _validate_property_id(property_id)
    if prop_err is not None:
        return prop_err

    try:
        check_writes_enabled()
    except WritesDisabledError as exc:
        return _fail(400, [str(exc)])

    raw = await file.read()
    if not raw:
        return _fail(400, ["Uploaded file is empty"])

    try:
        df = pd.read_csv(BytesIO(raw))
    except Exception as exc:
        logger.exception("unit_master import: CSV parse failed")
        return _fail(400, [f"Could not parse CSV: {exc}"])

    try:
        result = unit_service.import_unit_master(property_id, df, strict)
    except UnitMasterImportError as exc:
        # All-or-nothing: no created count, no partial payload (transaction rolled back).
        return _fail(422, exc.errors)
    except WritesDisabledError as exc:
        return _fail(400, [str(exc)])
    except Exception as exc:
        logger.exception("unit_master import: pipeline failed")
        return _fail(500, [f"Import failed: {exc}"])

    created = int(result.get("created", 0))
    body = UnitMasterResponse(
        success=True,
        data={"created": created},
        errors=[],
    ).model_dump()
    return JSONResponse(status_code=200, content=body)


@router.get("/")
async def list_property_units(
    property_id: int = Query(..., ge=1),
    active_only: bool = Query(True),
    user: dict = Depends(get_current_user),
):
    prop_err = _validate_property_id(property_id)
    if prop_err is not None:
        return prop_err

    try:
        rows = unit_service.list_all_units_for_property(property_id, active_only=active_only)
    except Exception as exc:
        logger.exception("unit_master list: failed")
        return _fail(500, [f"Could not list units: {exc}"])

    return _ok(data=_serialize(rows))


@router.post("/")
async def create_unit_manual(
    body: CreateUnitBody,
    property_id: int = Query(..., ge=1),
    user: dict = Depends(get_current_user),
):
    prop_err = _validate_property_id(property_id)
    if prop_err is not None:
        return prop_err

    code_raw = (body.unit_code or "").strip()
    if not code_raw:
        return _fail(400, ["unit_code is required"])

    norm = code_raw.upper()
    if unit_service.get_unit_by_code_norm(property_id, norm):
        return _fail(409, [f"Unit with code '{norm}' already exists for this property"])

    resolved_phase, place_err = _validate_create_placement(
        property_id, body.phase_id, body.building_id,
    )
    if place_err is not None:
        return place_err

    try:
        check_writes_enabled()
    except WritesDisabledError as exc:
        return _fail(400, [str(exc)])

    try:
        created = property_service.create_unit(
            property_id=property_id,
            unit_code_raw=code_raw,
            unit_code_norm=norm,
            unit_identity_key=norm,
            phase_id=resolved_phase,
            building_id=body.building_id,
            floor_plan=body.floor_plan,
            gross_sq_ft=body.gross_sq_ft,
            has_carpet=body.has_carpet,
            has_wd_expected=body.has_wd_expected,
        )
    except WritesDisabledError as exc:
        return _fail(400, [str(exc)])
    except Exception as exc:
        logger.exception("unit_master create_unit: failed")
        return _fail(400, [str(exc)])

    return _ok(data=_serialize(created))

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.deps import get_current_user
from services import property_service, scope_service
from services.write_guard import WritesDisabledError, check_writes_enabled

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/phase-scope", tags=["phase-scope"])


class PhaseScopeResponse(BaseModel):
    success: bool
    data: Any = None
    errors: list[str] = Field(default_factory=list)


class PutPhaseScopeBody(BaseModel):
    property_id: int
    phase_ids: list[int]


def _fail(status_code: int, errors: list[str]) -> JSONResponse:
    body = PhaseScopeResponse(success=False, data=None, errors=errors).model_dump()
    return JSONResponse(status_code=status_code, content=body)


def _ok(data: Any = None) -> dict[str, Any]:
    return PhaseScopeResponse(success=True, data=data, errors=[]).model_dump()


def _validate_property_id(property_id: int) -> JSONResponse | None:
    if property_id < 1:
        return _fail(400, ["property_id must be a positive integer"])
    if property_service.get_property_by_id(property_id) is None:
        return _fail(404, [f"Property {property_id} not found"])
    return None


@router.get("/")
def get_phase_scope(
    property_id: int = Query(..., ge=1),
    user: dict = Depends(get_current_user),
):
    err = _validate_property_id(property_id)
    if err is not None:
        return err

    uid = int(user["user_id"])
    try:
        phase_ids = scope_service.get_phase_scope(uid, property_id)
    except Exception as exc:
        logger.exception("phase_scope get: failed")
        return _fail(500, [f"Could not load phase scope: {exc}"])

    return _ok(data={"property_id": property_id, "phase_ids": phase_ids})


@router.put("/")
def put_phase_scope(
    body: PutPhaseScopeBody,
    user: dict = Depends(get_current_user),
):
    err = _validate_property_id(body.property_id)
    if err is not None:
        return err

    try:
        check_writes_enabled()
    except WritesDisabledError as exc:
        return _fail(400, [str(exc)])

    uid = int(user["user_id"])
    try:
        scope_service.update_phase_scope(uid, body.property_id, body.phase_ids)
    except ValueError as exc:
        return _fail(400, [str(exc)])
    except Exception as exc:
        logger.exception("phase_scope put: failed")
        return _fail(500, [f"Could not save phase scope: {exc}"])

    try:
        phase_ids = scope_service.get_phase_scope(uid, body.property_id)
    except Exception as exc:
        logger.exception("phase_scope put: reload failed")
        return _fail(500, [f"Scope saved but could not reload: {exc}"])

    return _ok(
        data={"property_id": body.property_id, "phase_ids": phase_ids},
    )

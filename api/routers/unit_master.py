from __future__ import annotations

import logging
from datetime import date, datetime
from io import BytesIO, StringIO
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.deps import get_current_user
from services import property_service, unit_service
from services.unit_master_import_plan import (
    build_unit_master_import_report,
    empty_unit_master_report,
    normalize_unit_master_report,
)
from services.unit_service import UnitMasterImportError
from services.write_guard import WritesDisabledError, check_writes_enabled

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/unit-master", tags=["unit-master"])

# Per legacy admin / unit master: normalized column name (str.strip + casefold) must match
# one of these to count as the unit key column. Maps to the ``unit_code`` name expected by
# ``unit_service.import_unit_master`` (Unit, unit, Unit Number, unit_number, UnitCode, Unit Code, …).
_UNIT_CODE_ALIAS_KEY_FOLDS: frozenset[str] = frozenset(
    {
        "unit",
        "unit number",
        "unit_number",
        "unitcode",
        "unit code",
        "unit_code",
    }
)


def _list_column_names(df: pd.DataFrame) -> list[str]:
    return [str(c) for c in df.columns]


def _df_has_resolvable_unit_column(df: pd.DataFrame) -> bool:
    """True if some column (trim + caseless) is a known unit_code alias (for read heuristics)."""
    for c in df.columns:
        if str(c).strip().casefold() in _UNIT_CODE_ALIAS_KEY_FOLDS:
            return True
    return False


def _normalize_unit_code_column_name_for_import(df: pd.DataFrame) -> pd.DataFrame:
    """If ``unit_code`` is not already a column name, rename the first matching alias column."""
    out = df.copy()
    if "unit_code" in out.columns:
        return out
    for col in out.columns:
        key = str(col).strip().casefold()
        if key in _UNIT_CODE_ALIAS_KEY_FOLDS:
            return out.rename(columns={col: "unit_code"})
    return out


def _read_unit_master_from_first_comma_line(raw: bytes) -> pd.DataFrame:
    """Re-parse: header row = first line in the file that contains a comma. ``dtype=str``."""
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    header_idx = next((i for i, line in enumerate(lines) if "," in line), None)
    if header_idx is None:
        raise ValueError("no line containing a comma (cannot locate CSV header row)")
    remainder = "\n".join(lines[header_idx:])
    return pd.read_csv(StringIO(remainder), dtype=str)


def _read_unit_master_csv(raw: bytes) -> pd.DataFrame:
    """Parse CSV: try ``read_csv`` on full bytes, then (if needed) first comma line as header. ``dtype=str``."""
    first_exc: Exception | None = None
    try:
        df = pd.read_csv(BytesIO(raw), dtype=str)
    except Exception as exc:
        first_exc = exc
        logger.info(
            "unit_master: primary read_csv failed (%s), trying header-row scan",
            exc,
        )
        try:
            return _read_unit_master_from_first_comma_line(raw)
        except Exception as retry_exc:
            assert first_exc is not None
            raise first_exc from retry_exc

    if not _df_has_resolvable_unit_column(df):
        try:
            alt = _read_unit_master_from_first_comma_line(raw)
        except Exception as exc:
            logger.info(
                "unit_master: skipped alternate header (primary had no unit column): %s",
                exc,
            )
            return df
        if _df_has_resolvable_unit_column(alt):
            return alt
    return df


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


def _fail(
    status_code: int,
    errors: list[str],
    data: Any = None,
) -> JSONResponse:
    body = UnitMasterResponse(success=False, data=data, errors=errors).model_dump()
    return JSONResponse(status_code=status_code, content=body)


def _prepare_dataframe_for_unit_import(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame | None, JSONResponse | None]:
    """Normalize a unit column alias to ``unit_code`` (legacy-compatible), then validate."""
    found_columns = _list_column_names(df)
    prepared = _normalize_unit_code_column_name_for_import(df)
    if "unit_code" not in prepared.columns:
        msg = "Missing required column: unit_code"
        return None, _fail(
            400,
            [msg],
            data={"message": msg, "found_columns": found_columns},
        )
    return prepared, None


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


def _ok(data: Any = None, errors: list[str] | None = None) -> dict[str, Any]:
    return UnitMasterResponse(
        success=True,
        data=data,
        errors=errors or [],
    ).model_dump()


def _unit_master_report_envelope(*, dry_run: bool, report: dict[str, Any]) -> dict[str, Any]:
    """Single contract for 200 dry-run and 422 gate responses (row-level + top-level)."""
    return {
        "dry_run": dry_run,
        "total_rows": int(report.get("total_rows", 0)),
        "valid_rows": int(report.get("valid_rows", 0)),
        "warning_rows": int(report.get("warning_rows", 0)),
        "error_rows": int(report.get("error_rows", 0)),
        "file_messages": list(report.get("file_messages") or []),
        "rows": list(report.get("rows") or []),
        "has_blocking_errors": bool(report.get("has_blocking_errors", False)),
    }


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
    dry_run: bool = Form(False),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    prop_err = _validate_property_id(property_id)
    if prop_err is not None:
        return prop_err

    raw = await file.read()
    if not raw:
        rep = normalize_unit_master_report(
            {
                **empty_unit_master_report(),
                "file_messages": ["File is empty (no data bytes)."],
            }
        )
        if dry_run:
            body = UnitMasterResponse(
                success=True,
                data={**_unit_master_report_envelope(dry_run=True, report=rep)},
                errors=[],
            ).model_dump()
            return JSONResponse(status_code=200, content=body)
        return _fail(
            422,
            ["File is empty; nothing to import."],
            data={"report": _unit_master_report_envelope(dry_run=False, report=rep)},
        )

    try:
        df = _read_unit_master_csv(raw)
    except Exception as exc:
        logger.exception("unit_master import: CSV parse failed")
        return _fail(400, [f"Could not parse CSV: {exc}"])

    prepared, prep_err = _prepare_dataframe_for_unit_import(df)
    if prep_err is not None:
        return prep_err
    assert prepared is not None
    df = prepared

    try:
        report = build_unit_master_import_report(property_id, df, strict)
    except Exception as exc:
        logger.exception("unit_master import: validation report failed")
        return _fail(500, [f"Validation failed: {exc}"])
    report = normalize_unit_master_report(report)

    if dry_run:
        body = UnitMasterResponse(
            success=True,
            data=_unit_master_report_envelope(dry_run=True, report=report),
            errors=[],
        ).model_dump()
        return JSONResponse(status_code=200, content=body)

    if report["has_blocking_errors"]:
        return _fail(
            422,
            ["Import blocked: one or more rows have errors."],
            data={"report": _unit_master_report_envelope(dry_run=False, report=report)},
        )

    try:
        check_writes_enabled()
    except WritesDisabledError as exc:
        return _fail(400, [str(exc)])

    try:
        result = unit_service.import_unit_master(property_id, df, strict)
    except UnitMasterImportError as exc:
        return _fail(422, exc.errors)
    except WritesDisabledError as exc:
        return _fail(400, [str(exc)])
    except Exception as exc:
        logger.exception("unit_master import: pipeline failed")
        return _fail(500, [f"Import failed: {exc}"])

    err_list = result.get("errors")
    if err_list is None:
        err_list = []
    body = UnitMasterResponse(
        success=True,
        data={
            "dry_run": False,
            "created": int(result.get("created", 0)),
            "skipped": int(result.get("skipped", 0)),
            "errors": list(err_list),
        },
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
        property_id,
        body.phase_id,
        body.building_id,
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

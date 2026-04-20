from __future__ import annotations

import base64
import json
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.deps import get_current_user
from services import (
    app_user_service,
    board_service,
    import_service,
    property_service,
    risk_service,
    system_settings_service,
)
from services.ai.ai_agent_chat_service import (
    AiAgentApiError,
    AiAgentConfigError,
    complete_chat,
)
from services.ai.ai_agent_context import build_context
from services.app_user_service import AppUserError
from services.exports import export_chart, export_excel, export_service
from services.report_operations import missing_move_out_service, override_conflict_service
from services.turnover_service import TurnoverError
from services.work_order_validator_service import build_report, get_summary, validate
from services.write_guard import WritesDisabledError

logger = logging.getLogger(__name__)

router = APIRouter()


def _serialize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _require_admin(user: dict) -> None:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


class ResolveMissingMoveOutRequest(BaseModel):
    unit_id: int
    move_out_date: date
    move_in_date: date | None = None


class FasNoteRequest(BaseModel):
    note_text: str


class SettingsPatchRequest(BaseModel):
    enable_db_write: bool


class CreatePropertyRequest(BaseModel):
    name: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str


class UpdateUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


@router.get("/operations/workflow/{property_id}")
async def get_workflow_summary(property_id: int, user: dict = Depends(get_current_user)):
    today = date.today()
    phase_scope = property_service.get_phases(property_id)
    scope_ids = [phase["phase_id"] for phase in phase_scope]
    board = board_service.get_board(property_id, today=today, phase_scope=scope_ids)
    summary = board_service.get_board_summary(property_id, today=today, phase_scope=scope_ids, board=board)
    metrics = board_service.get_board_metrics(property_id=property_id, today=today, phase_scope=scope_ids, board=board)
    risk_metrics = board_service.get_morning_risk_metrics(property_id, today=today, phase_scope=scope_ids)
    critical_units = board_service.get_todays_critical_units(property_id, today=today, phase_scope=scope_ids)
    import_timestamps = import_service.get_latest_import_timestamps(property_id)
    missing_move_outs = missing_move_out_service.list_missing_move_outs(property_id)
    return _serialize(
        {
            "today": today,
            "summary": summary,
            "metrics": metrics,
            "risk_metrics": risk_metrics,
            "critical_units": critical_units,
            "import_timestamps": import_timestamps,
            "missing_move_outs": missing_move_outs,
        }
    )


@router.get("/operations/risk/{property_id}")
async def get_risk_dashboard(property_id: int, user: dict = Depends(get_current_user)):
    rows = risk_service.get_risk_dashboard(property_id, today=date.today())
    rows.sort(key=lambda row: row["risk_score"], reverse=True)
    return _serialize({"rows": rows})


@router.get("/operations/flag-bridge/{property_id}")
async def get_flag_bridge(property_id: int, user: dict = Depends(get_current_user)):
    board = board_service.get_board_view(property_id, today=date.today())
    metrics = board_service.get_flag_bridge_metrics(board)
    return _serialize({"rows": board, "metrics": metrics})


@router.get("/operations/report-operations/{property_id}/missing-move-outs")
async def get_missing_move_outs(property_id: int, user: dict = Depends(get_current_user)):
    return _serialize({"rows": missing_move_out_service.list_missing_move_outs(property_id)})


@router.post("/operations/report-operations/{property_id}/missing-move-outs/{row_id}/resolve")
async def resolve_missing_move_out(
    property_id: int,
    row_id: int,
    body: ResolveMissingMoveOutRequest,
    user: dict = Depends(get_current_user),
):
    try:
        turnover = missing_move_out_service.resolve_missing_move_out(
            row_id=row_id,
            property_id=property_id,
            unit_id=body.unit_id,
            move_out_date=body.move_out_date,
            move_in_date=body.move_in_date,
            actor=user.get("username", "api"),
        )
    except (TurnoverError, WritesDisabledError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _serialize(turnover)


@router.get("/operations/report-operations/{property_id}/fas")
async def get_fas_rows(property_id: int, user: dict = Depends(get_current_user)):
    return _serialize({"rows": import_service.get_fas_rows(property_id)})


@router.patch("/operations/report-operations/fas/{row_id}")
async def patch_fas_note(
    row_id: int,
    body: FasNoteRequest,
    user: dict = Depends(get_current_user),
):
    from db.repository import import_repository

    with_rows = import_repository.update_row_note(row_id, body.note_text.strip())
    if with_rows is None:
        raise HTTPException(status_code=404, detail="FAS row not found")
    return _serialize(with_rows)


@router.get("/operations/report-operations/{property_id}/diagnostics")
async def get_diagnostics(property_id: int, user: dict = Depends(get_current_user)):
    batches = import_service.get_history(property_id, limit=50)
    rows = import_service.get_diagnostic_rows(property_id)
    overrides = override_conflict_service.list_override_conflicts(property_id)
    return _serialize({"batches": batches, "rows": rows, "overrides": overrides})


@router.get("/operations/admin/settings")
async def get_admin_settings(user: dict = Depends(get_current_user)):
    _require_admin(user)
    return {"enable_db_write": system_settings_service.get_enable_db_write()}


@router.patch("/operations/admin/settings")
async def patch_admin_settings(body: SettingsPatchRequest, user: dict = Depends(get_current_user)):
    _require_admin(user)
    system_settings_service.set_enable_db_write(body.enable_db_write)
    return {"enable_db_write": system_settings_service.get_enable_db_write()}


@router.post("/operations/admin/properties")
async def create_property(body: CreatePropertyRequest, user: dict = Depends(get_current_user)):
    logger.info(
        "create_property:request username=%s role=%s body=%r",
        user.get("username"),
        user.get("role"),
        body.model_dump(),
    )
    _require_admin(user)
    try:
        property_row = property_service.create_property(body.name.strip())
    except WritesDisabledError as exc:
        logger.warning(
            "create_property:writes_disabled type=%s message=%s",
            type(exc).__name__,
            str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "create_property:unhandled type=%s message=%s",
            type(exc).__name__,
            str(exc),
        )
        raise
    logger.info("create_property:success property_row=%r", property_row)
    return _serialize(property_row)


@router.get("/operations/admin/property-structure/{property_id}")
async def get_property_structure(property_id: int, user: dict = Depends(get_current_user)):
    phases = property_service.get_phases(property_id)
    structure: list[dict[str, Any]] = []
    for phase in phases:
        buildings = property_service.get_buildings(phase["phase_id"])
        structure.append(
            {
                "phase": phase,
                "buildings": [
                    {
                        "building": building,
                        "units": property_service.get_units_by_building(
                            property_id,
                            building["building_id"],
                            active_only=False,
                        ),
                    }
                    for building in buildings
                ],
            }
        )
    return _serialize({"structure": structure})


@router.get("/operations/admin/users")
async def list_admin_users(user: dict = Depends(get_current_user)):
    _require_admin(user)
    try:
        return _serialize({"rows": app_user_service.list_users()})
    except AppUserError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/operations/admin/users")
async def create_admin_user(body: CreateUserRequest, user: dict = Depends(get_current_user)):
    _require_admin(user)
    try:
        return _serialize(
            app_user_service.create_user(
                username=body.username,
                password=body.password,
                role=body.role,
            )
        )
    except (AppUserError, WritesDisabledError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/operations/admin/users/{user_id}")
async def patch_admin_user(user_id: int, body: UpdateUserRequest, user: dict = Depends(get_current_user)):
    _require_admin(user)
    try:
        if body.password is not None:
            return _serialize(app_user_service.set_password(user_id, body.password))
        if body.role is not None:
            return _serialize(app_user_service.change_role(user_id, body.role))
        if body.is_active is not None:
            return _serialize(app_user_service.set_active(user_id, body.is_active))
    except (AppUserError, WritesDisabledError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    raise HTTPException(status_code=400, detail="No update fields provided")


@router.get("/operations/exports/{property_id}/manifest")
async def get_export_manifest(property_id: int, user: dict = Depends(get_current_user)):
    return {
        "downloads": [
            {"key": "weekly-summary", "label": "Weekly Summary (TXT)", "href": f"/api/operations/exports/{property_id}/download/weekly-summary"},
            {"key": "dashboard-chart", "label": "Dashboard Chart (PNG)", "href": f"/api/operations/exports/{property_id}/download/dashboard-chart"},
            {"key": "final-report", "label": "Final Report (XLSX)", "href": f"/api/operations/exports/{property_id}/download/final-report"},
            {"key": "dmrb-report", "label": "DMRB Report (XLSX)", "href": f"/api/operations/exports/{property_id}/download/dmrb-report"},
            {"key": "all-reports", "label": "All Reports (ZIP)", "href": f"/api/operations/exports/{property_id}/download/all-reports"},
        ]
    }


def _build_export_parts(property_id: int) -> tuple[bytes, bytes, bytes, bytes]:
    today = date.today()
    rows = export_service.build_export_turnovers(property_id, today=today)
    metrics = board_service.get_board_metrics(property_id=property_id)
    summary_bytes = export_service.build_weekly_summary_bytes(property_id, today=today)
    chart_bytes = export_chart.build_dashboard_chart(rows, today=today)
    final_bytes = export_excel.build_final_report(rows)
    dmrb_bytes = export_excel.build_dmrb_report(rows, metrics, today)
    return final_bytes, dmrb_bytes, chart_bytes, summary_bytes


@router.get("/operations/exports/{property_id}/download/{asset}")
async def download_export(asset: str, property_id: int, user: dict = Depends(get_current_user)):
    final_bytes, dmrb_bytes, chart_bytes, summary_bytes = _build_export_parts(property_id)
    if asset == "weekly-summary":
        return Response(content=summary_bytes, media_type="text/plain", headers={"Content-Disposition": 'attachment; filename="Weekly_Summary.txt"'})
    if asset == "dashboard-chart":
        return Response(content=chart_bytes, media_type="image/png", headers={"Content-Disposition": 'attachment; filename="Dashboard_Chart.png"'})
    if asset == "final-report":
        return Response(content=final_bytes, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="Final_Report.xlsx"'})
    if asset == "dmrb-report":
        return Response(content=dmrb_bytes, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="DMRB_Report.xlsx"'})
    if asset == "all-reports":
        zip_bytes = export_service.build_all_exports_zip_from_parts(
            final_bytes=final_bytes,
            dmrb_bytes=dmrb_bytes,
            chart_bytes=chart_bytes,
            summary_bytes=summary_bytes,
        )
        return Response(content=zip_bytes, media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="DMRB_Reports.zip"'})
    raise HTTPException(status_code=404, detail="Unknown export asset")


@router.post("/operations/work-orders/validate")
async def validate_work_orders(
    property_id: int = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    content = await file.read()
    try:
        rows = validate(property_id, content)
        report_bytes = build_report(property_id, content)
        summary = get_summary(rows)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "summary": summary,
        "filename": "validated_work_orders.xlsx",
        "file_base64": base64.b64encode(report_bytes).decode("ascii"),
    }


@router.get("/operations/ai/stream")
async def stream_ai_reply(
    property_id: int,
    message: str,
    history: str | None = None,
    user: dict = Depends(get_current_user),
):
    try:
        parsed_history = json.loads(history) if history else []
        if not isinstance(parsed_history, list):
            parsed_history = []
    except json.JSONDecodeError:
        parsed_history = []

    messages = [msg for msg in parsed_history if isinstance(msg, dict)]
    messages.append({"role": "user", "content": message})

    def event_stream():
        try:
            context = build_context(property_id)
            reply = complete_chat(messages, app_context=context)
            for chunk in reply.split():
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk + ' '})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except (AiAgentConfigError, AiAgentApiError) as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

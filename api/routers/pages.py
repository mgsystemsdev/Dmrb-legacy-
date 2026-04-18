from __future__ import annotations
import time
from datetime import date
from fastapi import APIRouter, Request, Form, Query, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer
from config.settings import SECRET_KEY
from services import auth_service, board_service, property_service
from ui.helpers.formatting import (
    display_status_for_board_item,
    board_breach_row_display,
    nvm_label,
    format_date,
)

router = APIRouter()
templates = Jinja2Templates(directory="api/templates")

AUTH_COOKIE_NAME = "session"
_serializer = URLSafeTimedSerializer(SECRET_KEY)

_BOARD_FILTER_LABELS = {
    "SLA_RISK": "SLA Risk",
    "MOVE_IN_DANGER": "Move-In Danger",
    "INSPECTION_DELAY": "Inspection Delay",
    "PLAN_BREACH": "Plan Breach",
}

_PRIORITY_ROW_CSS = {
    "MOVE_IN_DANGER": "border-l-4 border-red-400",
    "SLA_RISK": "border-l-4 border-orange-400",
    "INSPECTION_DELAY": "border-l-4 border-yellow-400",
    "NORMAL": "",
    "LOW": "",
}

_READINESS_CSS = {
    "READY": "inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20",
    "IN_PROGRESS": "inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-600/20",
    "NOT_STARTED": "inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 ring-1 ring-inset ring-gray-500/10",
    "BLOCKED": "inline-flex items-center rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-600/20",
    "NO_TASKS": "inline-flex items-center rounded-full bg-gray-50 px-2 py-0.5 text-xs font-medium text-gray-400 ring-1 ring-inset ring-gray-400/10",
}

_READINESS_LABELS = {
    "READY": "Ready",
    "IN_PROGRESS": "In Progress",
    "NOT_STARTED": "Not Started",
    "BLOCKED": "Blocked",
    "NO_TASKS": "No Tasks",
}


def _prepare_row(item: dict) -> dict:
    t = item["turnover"]
    u = item.get("unit") or {}
    r = item["readiness"]
    breach = board_breach_row_display(item)
    priority = item["priority"]
    readiness_state = r["state"]
    return {
        "turnover_id": t["turnover_id"],
        "unit_code": u.get("unit_code_norm", "?"),
        "phase": u.get("phase_name", "—"),
        "lifecycle_phase": t.get("lifecycle_phase", ""),
        "status": display_status_for_board_item(item),
        "nvm": nvm_label(t.get("lifecycle_phase", "")),
        "readiness": readiness_state,
        "readiness_label": _READINESS_LABELS.get(readiness_state, readiness_state),
        "readiness_css": _READINESS_CSS.get(readiness_state, ""),
        "priority": priority,
        "priority_row_css": _PRIORITY_ROW_CSS.get(priority, ""),
        "dv": t.get("days_since_move_out"),
        "dtbr": t.get("days_to_move_in"),
        "move_in_date": format_date(t.get("move_in_date")),
        "tasks_done": r["completed"],
        "tasks_total": r["total"],
        "alert": breach.alert_display,
    }


def _apply_filters(rows: list[dict], filters: dict) -> list[dict]:
    if filters.get("search"):
        q = filters["search"].lower()
        rows = [r for r in rows if q in r["unit_code"].lower()]
    if filters.get("phase"):
        rows = [r for r in rows if r["phase"] == filters["phase"]]
    if filters.get("nvm"):
        rows = [r for r in rows if r["nvm"] == filters["nvm"]]
    if filters.get("readiness"):
        rows = [r for r in rows if r["readiness"] == filters["readiness"]]
    if filters.get("priority_filter"):
        rows = [r for r in rows if r["priority"] == filters["priority_filter"]]
    # board_filter passthrough (flag category filter)
    if filters.get("board_filter"):
        pass
        # filter_by_flag_category works on raw items; re-apply after row prep isn't clean,
        # so this passthrough is handled before _prepare_row in the calling route.
    return rows


# ── Login ─────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/board"):
    return templates.TemplateResponse("login.html", {"request": request, "next": next, "error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/board"),
):
    result = auth_service.authenticate(username, password)
    if not result:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "next": next, "error": "Invalid username or password"},
            status_code=401,
        )

    session_data = {
        "user_id": result["user_id"],
        "username": result["username"],
        "role": result["role"],
        "exp": int(time.time()) + 3600 * 24,
    }
    token = _serializer.dumps(session_data, salt="auth-session")
    redirect = RedirectResponse(url=next, status_code=303)
    redirect.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=3600 * 24,
    )
    return redirect


@router.get("/logout")
async def logout_page():
    redirect = RedirectResponse(url="/login", status_code=303)
    redirect.delete_cookie(AUTH_COOKIE_NAME)
    return redirect


# ── Board page ────────────────────────────────────────────────────────────────

@router.get("/board", response_class=HTMLResponse)
async def board_redirect(request: Request):
    props = property_service.get_all_properties()
    if not props:
        return templates.TemplateResponse(
            "board.html",
            {
                "request": request,
                "properties": [],
                "property_id": None,
                "phases": [],
                "filters": {},
                "row_count": 0,
                "board_filter_label": None,
                "board_filter_param": None,
            },
        )
    return RedirectResponse(url=f"/board/{props[0]['property_id']}", status_code=303)


@router.get("/board/{property_id}", response_class=HTMLResponse)
async def board_page(
    request: Request,
    property_id: int,
    board_filter: str = Query(""),
):
    props = property_service.get_all_properties()
    items = board_service.get_board_view(property_id, today=date.today())

    # Apply board_filter passthrough if set
    if board_filter:
        from services.board_service import filter_by_flag_category
        items = filter_by_flag_category(items, board_filter)

    rows = [_prepare_row(item) for item in items]
    phases = sorted({r["phase"] for r in rows if r["phase"] != "—"})

    board_filter_label = _BOARD_FILTER_LABELS.get(board_filter) if board_filter else None
    board_filter_param = f"board_filter={board_filter}" if board_filter else None

    return templates.TemplateResponse(
        "board.html",
        {
            "request": request,
            "properties": props,
            "property_id": property_id,
            "phases": phases,
            "filters": {},
            "row_count": len(rows),
            "board_filter_label": board_filter_label,
            "board_filter_param": board_filter_param,
        },
    )


# ── Board rows fragment (HTMX) ────────────────────────────────────────────────

@router.get("/api/board/{property_id}/rows", response_class=HTMLResponse)
async def board_rows(
    request: Request,
    property_id: int,
    search: str = Query(""),
    phase: str = Query(""),
    nvm: str = Query(""),
    readiness: str = Query(""),
    priority_filter: str = Query(""),
    board_filter: str = Query(""),
):
    items = board_service.get_board_view(property_id, today=date.today())

    if board_filter:
        from services.board_service import filter_by_flag_category
        items = filter_by_flag_category(items, board_filter)

    rows = [_prepare_row(item) for item in items]
    rows = _apply_filters(rows, {
        "search": search,
        "phase": phase,
        "nvm": nvm,
        "readiness": readiness,
        "priority_filter": priority_filter,
    })

    return templates.TemplateResponse(
        "board_row.html",
        {"request": request, "rows": rows},
    )

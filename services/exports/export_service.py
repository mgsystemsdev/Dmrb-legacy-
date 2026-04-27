"""Export generation — renderers over board service data (no report-specific DB queries)."""

from __future__ import annotations

import io
import math
import zipfile
from datetime import date, timedelta
from typing import Any

from domain import turnover_lifecycle as tl
from domain.readiness import READY
from services import board_service, property_service, scope_service

# Section titles (stable for tests and UI contract)
SECTION_KEY_METRICS = "Key Metrics"
SECTION_ALERTS = "Alerts"
SECTION_UPCOMING_MOVE_INS = "Upcoming Move-Ins"
SECTION_UPCOMING_READY = "Upcoming Ready"
SECTION_WD_NOT_INSTALLED = "W/D Not Installed"
SECTION_AGING = "Aging Distribution"

AGING_BUCKETS = ("1-10", "11-20", "21-30", "31-60", "61-120", "120+")


def is_finite_numeric(v: Any) -> bool:
    """True if *v* is safe to use in int()/bucket math (excludes None, NaN, inf, pandas NA)."""
    if v is None:
        return False
    try:
        import pandas as pd

        if pd.isna(v):
            return False
    except ImportError:
        pass
    except (TypeError, ValueError):
        pass
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError, OverflowError):
        return False


def _fmt_date(d: date | None) -> str:
    if d is None:
        return "—"
    return d.isoformat()


def _board_index(board: list[dict]) -> dict[int, dict]:
    return {item["turnover"]["turnover_id"]: item for item in board}


_TASK_LABEL: dict[str, str] = {
    "INSPECT": "Inspection",
    "CARPET_BID": "Carpet Bid",
    "MAKE_READY_BID": "Make Ready Bid",
    "PAINT": "Paint",
    "MAKE_READY": "Make Ready",
    "HOUSEKEEPING": "Housekeeping",
    "CARPET_CLEAN": "Carpet Clean",
    "FINAL_WALK": "Final Walk",
    "QUALITY_CONTROL": "Quality Control",
}

# Ordered task types matching the pipeline stages.
_PIPELINE_TASK_TYPES = [
    "INSPECT",
    "CARPET_BID",
    "MAKE_READY_BID",
    "PAINT",
    "MAKE_READY",
    "HOUSEKEEPING",
    "CARPET_CLEAN",
    "FINAL_WALK",
    "QUALITY_CONTROL",
]


def _aging_bucket(vacancy_days: int) -> str:
    if vacancy_days <= 10:
        return "1-10"
    if vacancy_days <= 20:
        return "11-20"
    if vacancy_days <= 30:
        return "21-30"
    if vacancy_days <= 60:
        return "31-60"
    if vacancy_days <= 120:
        return "61-120"
    return "120+"


def _find_task(tasks: list[dict], task_type: str) -> dict | None:
    for t in tasks:
        if t.get("task_type") == task_type:
            return t
    return None


def _qc_status(task_fw: dict | None) -> str:
    if task_fw is None:
        return "N/A"
    return "Confirmed" if task_fw.get("execution_status") == "COMPLETED" else "Pending"


def _completion_ratio(readiness: dict) -> float:
    total = readiness.get("total", 0)
    if not total:
        return 0.0
    return readiness.get("completed", 0) / total * 100


def _task_label(task_type: str) -> str:
    return _TASK_LABEL.get(task_type, task_type)


def _current_task_label(item: dict) -> str:
    blockers = item.get("readiness", {}).get("blockers") or []
    if not blockers:
        return "—"
    t0 = blockers[0]
    return str(t0.get("task_name") or t0.get("task_type") or "—")


def build_weekly_summary_text(
    property_id: int,
    today: date | None = None,
    phase_scope: list[int] | None = None,
    board: list | None = None,
    user_id: int = 0,
) -> str:
    """Plain-text weekly summary from a single board load + shared metrics."""
    today = today or date.today()
    if phase_scope is None:
        phase_scope = scope_service.get_phase_scope(user_id, property_id)
    if board is None:
        board = board_service.get_board(property_id, today=today, phase_scope=phase_scope)
    metrics = board_service.get_board_metrics(property_id=property_id, board=board)
    summary = board_service.get_board_summary(
        property_id, today=today, phase_scope=phase_scope, board=board
    )
    flag_units = board_service.get_flag_units(
        property_id, today=today, phase_scope=phase_scope, board=board
    )
    stalled_entries = board_service.work_stalled_unit_entries(board)
    by_tid = _board_index(board)

    active = metrics["active"]
    by_phase = summary["by_phase"]
    by_readiness = summary["by_readiness"]

    vacant = sum(by_phase.get(p, 0) for p in (tl.PHASE_VACANT_NOT_READY, tl.PHASE_VACANT_READY))
    on_notice = sum(by_phase.get(p, 0) for p in (tl.PHASE_ON_NOTICE, tl.PHASE_PRE_NOTICE))
    if active > 0:
        sla_ok = max(0, active - metrics["sla_breach"])
        sla_pct = round(100.0 * sla_ok / active, 1)
    else:
        sla_pct = 100.0
    ready_units = by_readiness.get(READY, 0)

    vac_values = [
        item["turnover"]["vacancy_days"]
        for item in board
        if item["turnover"].get("vacancy_days") is not None
    ]
    avg_vac = round(sum(vac_values) / len(vac_values), 1) if vac_values else 0.0

    lines: list[str] = []
    lines.append("DMRB Weekly Summary")
    lines.append(f"Property ID: {property_id}  |  As of: {_fmt_date(today)}")
    lines.append("")

    lines.append(SECTION_KEY_METRICS)
    lines.append("-" * len(SECTION_KEY_METRICS))
    lines.append(f"Total Active: {active}")
    lines.append(f"Vacant: {vacant}")
    lines.append(f"On Notice: {on_notice}")
    lines.append(f"SLA Compliance %: {sla_pct}")
    lines.append(f"Ready Units: {ready_units}")
    lines.append(f"Avg Days Vacant: {avg_vac}")
    lines.append("")

    lines.append(SECTION_ALERTS)
    lines.append("-" * len(SECTION_ALERTS))

    lines.append("SLA Breaches")
    for e in flag_units["SLA_BREACH"]:
        item = by_tid.get(e["turnover_id"])
        extra = ""
        if item:
            extra = f" | DV={item['turnover'].get('days_since_move_out', '—')}"
        lines.append(f"  - {e['unit_code']}{extra}")
    if not flag_units["SLA_BREACH"]:
        lines.append("  (none)")

    lines.append("Move-In Risk")
    for e in flag_units["MOVE_IN_DANGER"]:
        item = by_tid.get(e["turnover_id"])
        extra = ""
        if item:
            t = item["turnover"]
            extra = f" | move-in {_fmt_date(t.get('move_in_date'))} | DTM={t.get('days_to_move_in', '—')}"
        lines.append(f"  - {e['unit_code']}{extra}")
    if not flag_units["MOVE_IN_DANGER"]:
        lines.append("  (none)")

    lines.append("Stalled Tasks")
    for e in stalled_entries:
        item = by_tid.get(e["turnover_id"])
        ctx = f" | DV={e.get('dv')}"
        if item:
            ctx += f" | current: {_current_task_label(item)}"
        lines.append(f"  - {e['unit_code']}{ctx}")
    if not stalled_entries:
        lines.append("  (none)")

    lines.append("Plan Breaches")
    for e in flag_units["PLAN_BLOCKED"]:
        item = by_tid.get(e["turnover_id"])
        extra = ""
        if item:
            extra = f" | ready date {_fmt_date(item['turnover'].get('report_ready_date'))}"
        lines.append(f"  - {e['unit_code']}{extra}")
    if not flag_units["PLAN_BLOCKED"]:
        lines.append("  (none)")

    lines.append("")

    window_end = today + timedelta(days=7)
    lines.append(SECTION_UPCOMING_MOVE_INS)
    lines.append("-" * len(SECTION_UPCOMING_MOVE_INS))
    upcoming_mi = []
    for item in board:
        mid = item["turnover"].get("move_in_date")
        if mid is not None and today <= mid <= window_end:
            u = item.get("unit") or {}
            code = u.get("unit_code_norm") or "?"
            upcoming_mi.append((code, mid))
    upcoming_mi.sort(key=lambda x: x[1])
    for code, mid in upcoming_mi:
        lines.append(f"  - {code} | move-in {_fmt_date(mid)}")
    if not upcoming_mi:
        lines.append("  (none in next 7 days)")

    lines.append("")
    lines.append(SECTION_UPCOMING_READY)
    lines.append("-" * len(SECTION_UPCOMING_READY))
    upcoming_rd = []
    for item in board:
        rd = item["turnover"].get("report_ready_date")
        if rd is not None and today <= rd <= window_end:
            u = item.get("unit") or {}
            code = u.get("unit_code_norm") or "?"
            upcoming_rd.append((code, rd))
    upcoming_rd.sort(key=lambda x: x[1])
    for code, rd in upcoming_rd:
        lines.append(f"  - {code} | ready {_fmt_date(rd)}")
    if not upcoming_rd:
        lines.append("  (none in next 7 days)")

    lines.append("")
    lines.append(SECTION_WD_NOT_INSTALLED)
    lines.append("-" * len(SECTION_WD_NOT_INSTALLED))
    # Schema has only has_wd_expected; no persisted install flag yet.
    wd_rows = []
    for item in board:
        unit = item.get("unit")
        if unit and unit.get("has_wd_expected"):
            wd_rows.append(unit.get("unit_code_norm") or "?")
    wd_rows.sort()
    for code in wd_rows:
        lines.append(f"  - {code} | W/D expected (install status not tracked in DB)")
    if not wd_rows:
        lines.append("  (none)")

    lines.append("")
    lines.append(SECTION_AGING)
    lines.append("-" * len(SECTION_AGING))
    aging_counts = {b: 0 for b in AGING_BUCKETS}
    for item in board:
        vd = item["turnover"].get("vacancy_days")
        if not is_finite_numeric(vd):
            continue
        aging_counts[_aging_bucket(int(vd))] += 1
    for b in AGING_BUCKETS:
        lines.append(f"  {b}: {aging_counts[b]}")

    lines.append("")
    return "\n".join(lines)


def build_weekly_summary_bytes(
    property_id: int,
    today: date | None = None,
    phase_scope: list[int] | None = None,
    board: list | None = None,
    user_id: int = 0,
) -> bytes:
    return build_weekly_summary_text(
        property_id, today=today, phase_scope=phase_scope, board=board, user_id=user_id
    ).encode("utf-8")


def build_export_turnovers(
    property_id: int,
    today: date | None = None,
    phase_scope: list[int] | None = None,
    *,
    board: list | None = None,
    user_id: int = 0,
) -> list[dict]:
    """Flatten the board into export-ready rows. One dict per open turnover.

    Accepts an optional pre-loaded *board* so the caller can share a single
    board_service.get_board() result across all export builders.
    """
    today = today or date.today()
    if phase_scope is None:
        phase_scope = scope_service.get_phase_scope(user_id, property_id)
    if board is None:
        board = board_service.get_board(property_id, today=today, phase_scope=phase_scope)
    if not board:
        return []

    phases = property_service.get_phases(property_id)
    phase_map: dict[int, str] = {p["phase_id"]: p.get("name") or p["phase_code"] for p in phases}

    stalled_ids: set[int] = {
        e["turnover_id"] for e in board_service.work_stalled_unit_entries(board)
    }

    rows: list[dict] = []
    for item in board:
        turnover = item["turnover"]
        unit = item.get("unit") or {}
        tasks: list[dict] = item.get("tasks") or []
        readiness = item.get("readiness") or {
            "state": "NOT_STARTED",
            "completed": 0,
            "total": 0,
            "blockers": [],
        }
        sla = item.get("sla") or {"risk_level": "OK"}
        agreements = item.get("agreements") or {}
        notes = item.get("notes") or []

        unit_code = unit.get("unit_code_norm") or "?"
        phase_id = unit.get("phase_id")
        phase = phase_map.get(phase_id, str(phase_id) if phase_id is not None else "?")

        move_out_date = turnover.get("move_out_date")
        available_date = turnover.get("confirmed_move_out_date") or move_out_date

        task_insp = _find_task(tasks, "INSPECT")
        task_paint = _find_task(tasks, "PAINT")
        task_mr = _find_task(tasks, "MAKE_READY")
        task_hk = _find_task(tasks, "HOUSEKEEPING")
        task_carpet_clean = _find_task(tasks, "CARPET_CLEAN")
        task_fw = _find_task(tasks, "FINAL_WALK")
        task_qc = _find_task(tasks, "QUALITY_CONTROL")
        task_carpet_bid = _find_task(tasks, "CARPET_BID")
        task_mr_bid = _find_task(tasks, "MAKE_READY_BID")

        blockers: list[dict] = readiness.get("blockers") or []
        current_task = blockers[0] if blockers else None
        next_task = blockers[1] if len(blockers) > 1 else None

        wd_present = bool(unit.get("has_wd_expected"))
        wd_summary = "—" if not wd_present else "PENDING"

        turnover_id = turnover["turnover_id"]

        rows.append(
            {
                "turnover_id": turnover_id,
                "unit_code": unit_code,
                "phase": phase,
                "dv": turnover.get("vacancy_days"),
                "dtbr": turnover.get("days_to_be_ready"),
                "days_to_move_in": turnover.get("days_to_move_in"),
                "operational_state": turnover["lifecycle_phase"],
                "move_out_date": move_out_date,
                "move_in_date": turnover.get("move_in_date"),
                "report_ready_date": turnover.get("report_ready_date"),
                "available_date": available_date,
                "confirmed_move_out_date": turnover.get("confirmed_move_out_date"),
                "scheduled_move_out_date": turnover.get("scheduled_move_out_date"),
                "attention_badge": item["priority"],
                "sla_breach": sla.get("risk_level") == "BREACH",
                "plan_breach": agreements.get("plan") == "RED",
                "inspection_sla_breach": agreements.get("inspection") == "RED",
                "sla_movein_breach": agreements.get("move_in") == "RED",
                "is_task_stalled": turnover_id in stalled_ids,
                "task_completion_ratio": _completion_ratio(readiness),
                "is_unit_ready": readiness.get("state") == READY,
                "wd_present": wd_present,
                "wd_summary": wd_summary,
                "notes_joined": "; ".join(t["text"] for t in notes if t.get("text")),
                # Task objects (None if task type not present for this turnover)
                "task_insp": task_insp,
                "task_paint": task_paint,
                "task_mr": task_mr,
                "task_hk": task_hk,
                "task_carpet_clean": task_carpet_clean,
                "task_fw": task_fw,
                "task_qc": task_qc,
                "task_carpet_bid": task_carpet_bid,
                "task_mr_bid": task_mr_bid,
                # Derived from FINAL_WALK task execution_status
                "qc_status": _qc_status(task_fw),
                # First and second blocking tasks (task dicts or None)
                "current_task": current_task,
                "next_task": next_task,
                # Raw tasks list — used in Schedule/Upcoming sheets
                "tasks_list": tasks,
            }
        )
    rows.sort(
        key=lambda r: (
            r["move_in_date"] is None,
            r["move_in_date"] or date.max,
            -int(r["dv"]) if is_finite_numeric(r.get("dv")) else 0,
        )
    )
    return rows


def build_all_exports_zip_from_parts(
    final_bytes: bytes,
    dmrb_bytes: bytes,
    chart_bytes: bytes,
    summary_bytes: bytes,
) -> bytes:
    """Package the four pre-built export artifacts into a single ZIP."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("Final_Report.xlsx", final_bytes)
        zf.writestr("DMRB_Report.xlsx", dmrb_bytes)
        zf.writestr("Dashboard_Chart.png", chart_bytes)
        zf.writestr("Weekly_Summary.txt", summary_bytes)
    return buf.getvalue()

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Union

from domain.turnover_lifecycle import nvm_state  # noqa: F401  (re-exported)

_PRIORITY_COLORS = {
    "MOVE_IN_DANGER": "🔴 Move-in Danger",
    "SLA_RISK": "🟠 SLA Risk",
    "INSPECTION_DELAY": "🟡 Inspection Delay",
    "NORMAL": "🔵 Normal",
    "LOW": "⚪ Low",
}

_READINESS_BADGES = {
    "READY": "✅ Ready",
    "BLOCKED": "🚫 Blocked",
    "IN_PROGRESS": "🔄 In Progress",
    "NOT_STARTED": "⬜ Not Started",
    "NO_TASKS": "➖ No Tasks",
}

_PHASE_LABELS = {
    "PRE_NOTICE": "Pre-Notice",
    "ON_NOTICE": "On Notice",
    "VACANT_NOT_READY": "Vacant Not Ready",
    "VACANT_READY": "Vacant Ready",
    "OCCUPIED": "Occupied",
    "CLOSED": "Closed",
    "CANCELED": "Canceled",
}

_SLA_INDICATORS = {
    "OK": "✅ OK",
    "WARNING": "⚠️ Warning",
    "BREACH": "🚨 Breach",
}


def format_date(d: Optional[Union[date, datetime]]) -> str:
    if d is None:
        return "—"
    return d.isoformat()


def format_datetime(ts: Optional[datetime]) -> str:
    """Format a timestamp for display. Returns '—' if None."""
    if ts is None:
        return "—"
    if hasattr(ts, "strftime"):
        return ts.strftime("%Y-%m-%d %H:%M")
    return str(ts)


def format_completed_date(d: Optional[Union[date, datetime]]) -> str:
    """Format a date for Completed At column (MM/DD/YYYY). Returns '—' if None."""
    if d is None:
        return "—"
    if hasattr(d, "strftime"):
        return d.strftime("%m/%d/%Y")
    return str(d)


def format_days(n: Optional[int]) -> str:
    if n is None:
        return "—"
    return f"{n}d"


_DV_SLA_THRESHOLD = 10


def format_dv(days: int | None, threshold: int = _DV_SLA_THRESHOLD) -> str:
    """Format Days Vacant with red highlight when over threshold."""
    if days is None:
        return "—"
    if days > threshold:
        return f":red[**{days}d**]"
    return f"{days}d"


def priority_color(level: str) -> str:
    return _PRIORITY_COLORS.get(level, level)


def readiness_badge(state: str) -> str:
    return _READINESS_BADGES.get(state, state)


def phase_label(phase: str) -> str:
    return _PHASE_LABELS.get(phase, phase)


def sla_indicator(risk_level: str) -> str:
    return _SLA_INDICATORS.get(risk_level, risk_level)


_NVM_MAP = {
    "PRE_NOTICE": "Notice",
    "ON_NOTICE": "Notice + SMI",
    "VACANT_NOT_READY": "Vacant",
    "VACANT_READY": "Vacant",
    "OCCUPIED": "Move-In",
    "CLOSED": "—",
    "CANCELED": "—",
}


def nvm_label(phase: str) -> str:
    """Map lifecycle phase to Notice/Vacant/Move-in grouping."""
    return _NVM_MAP.get(phase, "—")


_STATUS_LABELS = {
    "PRE_NOTICE": "On notice",
    "ON_NOTICE": "On notice",
    "VACANT_NOT_READY": "Vacant not ready",
    "VACANT_READY": "Vacant ready",
    "OCCUPIED": "Vacant ready",
    "CLOSED": "Vacant ready",
    "CANCELED": "Vacant not ready",
}

_MANUAL_STATUS_TO_BOARD_LABEL = {
    "on notice": "On notice",
    "on notice (break)": "On notice",
    "vacant not ready": "Vacant not ready",
    "vacant ready": "Vacant ready",
}


def status_label(phase: str) -> str:
    """Human-friendly status string for the board."""
    return _STATUS_LABELS.get(phase, phase)


BOARD_INSPECTION_TASK_TYPES = frozenset({"INSPECT", "INSPECTION"})


@dataclass(frozen=True)
class BoardBreachDisplay:
    """Dot columns + Alert string for board row and Flag Bridge (shared rules)."""

    alert_display: str
    mi_display: str
    insp_display: str
    is_viol: bool
    is_sla: bool
    is_plan: bool


def board_breach_row_display(item: dict) -> BoardBreachDisplay:
    """Breaches, MI/Insp dots, and Alert ladder — same logic for main board and Flag Bridge.

    Vacant-ready detection uses phase, raw availability, and effective_* fields so Alert
    stays aligned with the Status column. On-notice uses the same display status label.
    """
    turnover = item["turnover"]
    phase = turnover["lifecycle_phase"]
    priority = item["priority"]
    agreements = item.get("agreements") or {}

    if agreements:
        is_viol = agreements.get("viol") == "RED"
        is_insp = agreements.get("inspection") == "RED"
        is_sla = agreements.get("sla") == "RED"
        is_mi = agreements.get("move_in") == "RED"
        is_plan = agreements.get("plan") == "RED"
    else:
        sla_level = item["sla"]["risk_level"]
        readiness_st = item["readiness"]["state"]
        pressure = item["sla"].get("move_in_pressure")
        is_viol = priority in ("MOVE_IN_DANGER", "SLA_RISK")
        is_insp = priority == "INSPECTION_DELAY"
        is_sla = priority == "SLA_RISK" or sla_level in ("WARNING", "BREACH")
        is_mi = pressure is not None and pressure <= 3
        is_plan = (
            readiness_st == "BLOCKED"
            and priority not in ("MOVE_IN_DANGER", "SLA_RISK")
        )

    def _dot(red: bool) -> str:
        return "🔴" if red else "🟢"

    eff_m = (turnover.get("effective_manual_ready_status") or "").strip().lower()
    eff_a = (turnover.get("effective_availability_status") or "").strip().lower()
    raw_a = (turnover.get("availability_status") or "").strip().lower()
    is_vacant_ready = (
        phase == "VACANT_READY"
        or raw_a in ("vacant ready", "beacon ready")
        or eff_m == "vacant ready"
        or eff_a in ("vacant ready", "beacon ready")
    )

    mi_display = "—" if not turnover.get("move_in_date") else _dot(is_mi)

    tasks_raw = item.get("tasks")
    if tasks_raw is None:
        has_incomplete_tasks = True
        tasks: list[dict] = []
    else:
        tasks = tasks_raw
        has_incomplete_tasks = any(
            t.get("execution_status") != "COMPLETED" for t in tasks
        )

    inspection_task = next(
        (t for t in tasks if t.get("task_type") in BOARD_INSPECTION_TASK_TYPES),
        None,
    )

    status_display = display_status_for_board_item(item)
    if status_display == "Vacant not ready":
        insp_completed = inspection_task and inspection_task.get("execution_status") == "COMPLETED"
        if insp_completed:
            insp_display = "🟢"
        else:
            dv = turnover.get("days_since_move_out")
            dv_days = dv if dv is not None else 0
            if dv_days >= 2:
                insp_display = "🔴"
            elif dv_days > 0:
                insp_display = "🟡"
            else:
                insp_display = "—"
    else:
        insp_display = _dot(is_insp)

    breach_parts: list[str] = []
    if is_sla:
        breach_parts.append("⏰ SLA")
    if mi_display == "🔴":
        breach_parts.append("🚨 MI")
    if insp_display == "🔴":
        breach_parts.append("🔍 Insp")
    if is_plan:
        breach_parts.append("📋 Plan")
    alert_display = " | ".join(breach_parts) if breach_parts else ""

    is_on_notice = status_display == "On notice"

    if not (alert_display and alert_display.strip()):
        if is_vacant_ready:
            alert_display = "✅ Ready"
        elif is_on_notice:
            alert_display = "📢 On Notice"
        elif has_incomplete_tasks:
            alert_display = "🔧 In Progress"
        else:
            alert_display = "⚠️ Needs Attention"

    return BoardBreachDisplay(
        alert_display=alert_display,
        mi_display=mi_display,
        insp_display=insp_display,
        is_viol=is_viol,
        is_sla=is_sla,
        is_plan=is_plan,
    )


def display_status_for_board_item(item: dict) -> str:
    """Status string for board/flag_bridge tables and filters."""
    turnover = item.get("turnover") or {}
    effective = turnover.get("effective_manual_ready_status")
    if effective:
        normalized = _MANUAL_STATUS_TO_BOARD_LABEL.get(str(effective).strip().lower())
        if normalized:
            return normalized
        return str(effective)
    return status_label(turnover.get("lifecycle_phase") or "")


def alert_icon(priority: str) -> str:
    """Return alert emoji for board alert column."""
    if priority == "MOVE_IN_DANGER":
        return "🔴"
    if priority == "SLA_RISK":
        return "⚠️"
    if priority == "INSPECTION_DELAY":
        return "🟡"
    return ""


def qc_label(tasks: list[dict]) -> str:
    """QC status: Confirmed when all completed tasks have manager_confirmed_at."""
    completed = [task for task in tasks if task["execution_status"] == "COMPLETED"]
    if not completed:
        return "Pending"
    all_confirmed = all(task.get("manager_confirmed_at") is not None for task in completed)
    return "Confirmed" if all_confirmed else "Pending"

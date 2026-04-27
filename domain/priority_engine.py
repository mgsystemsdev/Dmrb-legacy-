"""Priority engine.

Computes an operational priority level for each open turnover.
Pure functions — no database access, no Streamlit imports.

Priority tiers (highest to lowest):

    1. MOVE_IN_DANGER  — move-in is imminent or overdue and unit is not ready
    2. SLA_RISK        — SLA breach threshold approaching or exceeded
    3. INSPECTION_DELAY — tasks are blocked awaiting inspection/confirmation
    4. NORMAL          — work in progress, on track
    5. LOW             — pre-notice or no urgency
"""

from __future__ import annotations

from datetime import date

from domain.readiness import BLOCKED, NOT_STARTED, READY, readiness_state
from domain.sla import DEFAULT_SLA_THRESHOLD_DAYS, SLA_BREACH, SLA_WARNING, sla_risk
from domain.turnover_lifecycle import (
    PHASE_CANCELED,
    PHASE_CLOSED,
    PHASE_ON_NOTICE,
    PHASE_PRE_NOTICE,
    PHASE_VACANT_READY,
    days_to_move_in,
    lifecycle_phase,
)

# ── Priority Levels ─────────────────────────────────────────────────────────

MOVE_IN_DANGER = "MOVE_IN_DANGER"
SLA_RISK_LEVEL = "SLA_RISK"
INSPECTION_DELAY = "INSPECTION_DELAY"
PLAN_DELAY = "PLAN_DELAY"
NORMAL = "NORMAL"
LOW = "LOW"

PRIORITY_ORDER = [
    MOVE_IN_DANGER,
    SLA_RISK_LEVEL,
    INSPECTION_DELAY,
    PLAN_DELAY,
    NORMAL,
    LOW,
]

MOVE_IN_DANGER_DAYS = 3


def derive_priority_from_agreements(agreements: dict) -> str:
    """Derive a single priority label from agreement flags (Phase 5).

    Priority is a summary for sorting and display; it does not modify agreements.
    Severity order: move_in > sla > inspection > plan > NORMAL.

    Args:
        agreements: dict with keys inspection, sla, move_in, plan (values GREEN | YELLOW | RED).

    Returns:
        One of MOVE_IN_DANGER, SLA_RISK, INSPECTION_DELAY, PLAN_DELAY, NORMAL.
    """
    if agreements.get("move_in") == "RED":
        return MOVE_IN_DANGER
    if agreements.get("sla") == "RED":
        return SLA_RISK_LEVEL
    if agreements.get("inspection") == "RED":
        return INSPECTION_DELAY
    if agreements.get("plan") == "RED":
        return PLAN_DELAY
    return NORMAL


def urgency_sort_key(
    priority: str,
    turnover: dict,
    today: date | None = None,
) -> tuple[int, int]:
    """Return a sort key: move-in units first, then by DV descending.

    Group 0 — units WITH a move-in date: sorted by move-in ascending (closest first).
    Group 1 — units WITHOUT a move-in date: sorted by DV descending (longest vacant first).
    """
    today = today or date.today()
    move_in = turnover.get("move_in_date")
    if move_in is not None and (not hasattr(move_in, "year") or move_in.year >= 1990):
        return (0, move_in.toordinal())
    dv = turnover.get("days_since_move_out")
    if dv is None:
        from domain.turnover_lifecycle import days_since_move_out

        dv = days_since_move_out(turnover, today) or 0
    return (1, -dv)


def priority_level(
    turnover: dict,
    tasks: list[dict],
    today: date | None = None,
    sla_threshold: int = DEFAULT_SLA_THRESHOLD_DAYS,
) -> str:
    """Evaluate the operational priority for one turnover.

    Args:
        turnover: turnover dict from the repository.
        tasks: task list for this turnover from task_repository.
        today: reference date (defaults to today).
        sla_threshold: SLA breach threshold in days.

    Returns:
        One of the priority level constants.
    """
    today = today or date.today()
    phase = lifecycle_phase(turnover, today)

    if phase in (PHASE_CLOSED, PHASE_CANCELED):
        return LOW

    readiness = readiness_state(tasks)

    if readiness == READY and phase == PHASE_VACANT_READY:
        return LOW

    remaining = days_to_move_in(turnover, today)
    if remaining is not None and remaining <= MOVE_IN_DANGER_DAYS and readiness != READY:
        return MOVE_IN_DANGER

    sla = sla_risk(turnover, today, sla_threshold)
    if sla in (SLA_BREACH, SLA_WARNING):
        return SLA_RISK_LEVEL

    if readiness == BLOCKED:
        return INSPECTION_DELAY

    if phase in (PHASE_PRE_NOTICE, PHASE_ON_NOTICE):
        return LOW if readiness in (READY, NOT_STARTED) else NORMAL

    return NORMAL


def priority_sort_key(
    turnover: dict,
    tasks: list[dict],
    today: date | None = None,
    sla_threshold: int = DEFAULT_SLA_THRESHOLD_DAYS,
) -> tuple[int, int]:
    """Return a sort key: move-out date ascending, then DV descending.

    Same ordering as urgency_sort_key; kept for backward compatibility.
    """
    today = today or date.today()
    level = priority_level(turnover, tasks, today, sla_threshold)
    return urgency_sort_key(level, turnover, today)


def evaluate_board(
    turnovers_with_tasks: list[tuple[dict, list[dict]]],
    today: date | None = None,
    sla_threshold: int = DEFAULT_SLA_THRESHOLD_DAYS,
) -> list[dict]:
    """Evaluate and sort a full board of turnovers by priority.

    Args:
        turnovers_with_tasks: list of (turnover_dict, tasks_list) tuples.
        today: reference date.
        sla_threshold: SLA breach threshold.

    Returns:
        List of dicts with keys: turnover, tasks, priority, rank.
        Sorted highest priority first.
    """
    today = today or date.today()
    results = []
    for turnover, tasks in turnovers_with_tasks:
        level = priority_level(turnover, tasks, today, sla_threshold)
        key = priority_sort_key(turnover, tasks, today, sla_threshold)
        results.append(
            {
                "turnover": turnover,
                "tasks": tasks,
                "priority": level,
                "rank": key,
            }
        )
    results.sort(key=lambda r: r["rank"])
    return results

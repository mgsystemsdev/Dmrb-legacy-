"""Board service — assembles the full operational board for a property.

Before reading turnover/task rows, get_board runs the same reconciliation as
services.board_reconciliation.run_board_reconciliation_for_property (AU heal,
on-notice turnover creation, lifecycle transition, ready-date backfill, task
backfill). For headless rebuilds, call that function explicitly after imports;
loading the board in Streamlit also satisfies the contract.
"""

from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)

from db.repository import (
    turnover_repository,
    task_repository,
    unit_repository,
    risk_repository,
    note_repository,
)
from domain import turnover_lifecycle, readiness as readiness_domain, sla as sla_domain
from domain.availability_status import (
    effective_availability_status,
    effective_manual_ready_status,
)
from domain.readiness import READY, BLOCKED, IN_PROGRESS, NOT_STARTED, NO_TASKS
from domain.sla import SLA_OK
from domain.turnover_lifecycle import PHASE_VACANT_READY, PHASE_PRE_NOTICE
from services import scope_service
from domain.priority_engine import (
    derive_priority_from_agreements,
    urgency_sort_key,
    PRIORITY_ORDER,
    DEFAULT_SLA_THRESHOLD_DAYS,
)


# Agreement evaluation (Phase 4): task types treated as "inspection" for inspection agreement
INSPECTION_TASK_TYPES = frozenset({"INSPECT", "INSPECTION"})
# SLA threshold in days for the Turnaround SLA agreement (spec: 10 days)
AGREEMENT_SLA_DAYS = 10

# All-green agreements when guard rails apply (Rule 1 Vacant Ready, Rule 2 No Move-Out, Rule 3 Cancelled)
AGREEMENTS_ALL_GREEN = {
    "inspection": "GREEN",
    "sla": "GREEN",
    "move_in": "GREEN",
    "plan": "GREEN",
    "viol": "GREEN",
}


def evaluate_turnover_agreements(
    turnover: dict,
    tasks: list[dict],
    today: date,
    sla_threshold_days: int = AGREEMENT_SLA_DAYS,
) -> dict:
    """Evaluate all operational agreements for a single turnover. Flags are independent.

    Returns a dict with keys: inspection, sla, move_in, plan, viol.
    Values: "GREEN" | "YELLOW" (inspection only) | "RED".
    """
    readiness = readiness_domain.readiness_state(tasks)
    blockers = readiness_domain.blocking_tasks(tasks)
    days_out = turnover_lifecycle.days_since_move_out(turnover, today)
    days_in = turnover_lifecycle.days_to_move_in(turnover, today)
    ready_plan_date = turnover.get("report_ready_date")

    # Inspection agreement
    inspection_tasks = [t for t in tasks if t.get("task_type") in INSPECTION_TASK_TYPES]
    if not inspection_tasks:
        inspection_flag = "GREEN"
    else:
        inspection_done = any(
            t["execution_status"] == "COMPLETE" for t in inspection_tasks
        )
        if inspection_done:
            inspection_flag = "GREEN"
        else:
            non_inspection_blockers = [
                t for t in blockers if t.get("task_type") not in INSPECTION_TASK_TYPES
            ]
            if non_inspection_blockers:
                inspection_flag = "GREEN"  # work still in progress
            elif days_out is None:
                inspection_flag = "GREEN"
            elif days_out > 48:
                inspection_flag = "RED"
            elif days_out > 24:
                inspection_flag = "YELLOW"
            else:
                inspection_flag = "GREEN"

    # SLA agreement: 10 days since move-out, unit must be READY
    if days_out is not None and days_out > sla_threshold_days and readiness != READY:
        sla_flag = "RED"
    else:
        sla_flag = "GREEN"

    # Move-in agreement: move-in within 3 days and not READY
    if (
        turnover.get("move_in_date") is not None
        and days_in is not None
        and days_in <= 3
        and readiness != READY
    ):
        move_in_flag = "RED"
    else:
        move_in_flag = "GREEN"

    # Plan agreement: past report_ready_date and not READY
    if (
        ready_plan_date is not None
        and today > ready_plan_date
        and readiness != READY
    ):
        plan_flag = "RED"
    else:
        plan_flag = "GREEN"

    # Viol: derived from SLA or move-in critical
    viol_flag = "RED" if (sla_flag == "RED" or move_in_flag == "RED") else "GREEN"

    return {
        "inspection": inspection_flag,
        "sla": sla_flag,
        "move_in": move_in_flag,
        "plan": plan_flag,
        "viol": viol_flag,
    }


def get_board_filter_options() -> dict:
    """Return filter dropdown options (priority, phase, readiness) for board/flag-bridge UI.
    Keeps domain ordering and constants out of the UI layer."""
    return {
        "priority_order": list(PRIORITY_ORDER),
        "phase_order": list(turnover_lifecycle.PHASE_ORDER),
        "readiness_states": [READY, BLOCKED, IN_PROGRESS, NOT_STARTED, NO_TASKS],
    }


def _evaluation_gate(turnover: dict, today: date) -> str | None:
    """Guard rails (evaluate first): determine if turnover bypasses agreement evaluation.

    Rule 1 — Vacant Ready Override: If unit status is Vacant Ready, pipeline is finished.
    All agreements (Viol, Inspection, SLA, Move-In, Plan) evaluate to green. Unit remains
    visible with no problems. Turnover does NOT close at Vacant Ready (remains open until
    move-in or cancellation).

    Rule 2 — No Move-Out: If no move-out date exists, there is no turnover yet. Unit is
    not evaluated by Flag Bridge rules (no violations shown).

    Rule 3 — Cancelled Turnover: If turnover is cancelled, lifecycle stops. Unit is
    excluded from evaluation (no violations shown).

    Returns:
        "skip_evaluation" — Rule 2 or 3: do not run agreement evaluation (all green).
        "vacant_ready" — Rule 1: treat as all green, unit still on board.
        None — proceed with full agreement evaluation.
    """
    # Rule 3: Cancelled → excluded from evaluation
    if turnover.get("canceled_at"):
        return "skip_evaluation"
    # Rule 2: No move-out → not evaluated by Flag Bridge rules
    if turnover.get("move_out_date") is None:
        return "skip_evaluation"
    # Rule 1: Vacant Ready → all agreements satisfied, unit visible, no problems.
    # Use effective status so On Notice + date passed is not gated as vacant_ready.
    phase = turnover_lifecycle.lifecycle_phase(turnover, today)
    if phase == PHASE_VACANT_READY:
        return "vacant_ready"
    avail = (effective_availability_status(turnover, today) or turnover.get("availability_status") or "").strip().lower()
    if avail in ("vacant ready", "beacon ready"):
        return "vacant_ready"
    return None


def _build_healthy_board_item(
    turnover: dict,
    unit: dict | None,
    tasks: list[dict],
    today: date,
    gate_result: str,
    risks: list,
    notes: list,
) -> dict:
    """Build a board item with healthy defaults (no violations). Used when guard rails apply."""
    if gate_result == "skip_evaluation":
        phase = PHASE_PRE_NOTICE
        days_out = None
        days_in = None
        vac_days = None
        dtbr = None
    else:
        assert gate_result == "vacant_ready"
        phase = turnover_lifecycle.lifecycle_phase(turnover, today)
        days_out = turnover_lifecycle.days_since_move_out(turnover, today)
        days_in = turnover_lifecycle.days_to_move_in(turnover, today)
        vac_days = turnover_lifecycle.vacancy_days(turnover, today)
        dtbr = turnover_lifecycle.days_to_be_ready(turnover, tasks, today)

    sort_key = urgency_sort_key("NORMAL", turnover, today)

    return {
        "turnover": {
            **turnover,
            "lifecycle_phase": phase,
            "days_since_move_out": days_out,
            "days_to_move_in": days_in,
            "vacancy_days": vac_days,
            "days_to_be_ready": dtbr,
            "effective_manual_ready_status": effective_manual_ready_status(turnover, today),
            "effective_availability_status": effective_availability_status(turnover, today),
        },
        "unit": unit,
        "tasks": tasks,
        "readiness": {
            "state": READY,
            "completed": 0,
            "total": 0,
            "blockers": [],
        },
        "sla": {
            "risk_level": SLA_OK,
            "days_until_breach": None,
            "move_in_pressure": None,
        },
        "priority": "NORMAL",
        "agreements": AGREEMENTS_ALL_GREEN,
        "risks": risks,
        "notes": notes,
        "_sort_key": sort_key,
    }


def get_board(
    property_id: int,
    today: date | None = None,
    sla_threshold: int = DEFAULT_SLA_THRESHOLD_DAYS,
    phase_scope: list[int] | None = None,
) -> list[dict]:
    """Build the full board for a property.

    Returns a list of board items sorted highest-priority first.
    Each item contains:
      - turnover: the turnover row with computed lifecycle fields
      - unit: the unit row
      - tasks: task list
      - readiness: readiness summary
      - sla: SLA evaluation
      - priority: priority level string
      - risks: open risk flags
      - notes: open notes

    When phase_scope is set, only turnovers whose unit is in one of those phases are included.

    Before querying turnovers, runs ``run_board_reconciliation_for_property`` (see
    ``services.board_reconciliation``) so headless rebuilds can call that function
    alone after imports with the same *today* and phase scope.
    """
    today = today or date.today()
    # Lazy import avoids circular import: board_reconciliation → turnover_service → risk_service → board_service.
    from services.board_reconciliation import run_board_reconciliation_for_property

    run_board_reconciliation_for_property(
        property_id,
        today=today,
        phase_ids=phase_scope,
    )
    turnovers = turnover_repository.get_open_by_property(property_id, phase_ids=phase_scope)
    if not turnovers:
        return []

    units_by_id = {}
    units = unit_repository.get_by_property(
        property_id, active_only=False, phase_ids=phase_scope
    )
    for u in units:
        units_by_id[u["unit_id"]] = u

    turnover_ids = [t["turnover_id"] for t in turnovers]
    tasks_by_turnover = task_repository.get_by_turnover_ids(turnover_ids)
    risks_by_turnover = risk_repository.get_open_by_turnover_ids(turnover_ids)
    notes_by_turnover = note_repository.get_by_turnover_ids(turnover_ids)

    board = []
    for turnover in turnovers:
        tasks = tasks_by_turnover.get(turnover["turnover_id"], [])
        risks = risks_by_turnover.get(turnover["turnover_id"], [])
        notes = notes_by_turnover.get(turnover["turnover_id"], [])
        unit = units_by_id.get(turnover["unit_id"])

        gate = _evaluation_gate(turnover, today)
        if gate in ("skip_evaluation", "vacant_ready"):
            board.append(
                _build_healthy_board_item(
                    turnover, unit, tasks, today, gate, risks, notes
                )
            )
            continue

        phase = turnover_lifecycle.lifecycle_phase(turnover, today)
        days_out = turnover_lifecycle.days_since_move_out(turnover, today)
        days_in = turnover_lifecycle.days_to_move_in(turnover, today)
        vac_days = turnover_lifecycle.vacancy_days(turnover, today)
        dtbr = turnover_lifecycle.days_to_be_ready(turnover, tasks, today)

        state = readiness_domain.readiness_state(tasks)
        completed, total = readiness_domain.completion_ratio(tasks)
        blockers = readiness_domain.blocking_tasks(tasks)

        risk_level = sla_domain.sla_risk(turnover, today, sla_threshold)
        remaining = sla_domain.days_until_breach(turnover, today, sla_threshold)
        pressure = sla_domain.move_in_pressure(turnover, today)

        # Agreement evaluation first (Phase 4), then derive priority (Phase 5)
        agreements = evaluate_turnover_agreements(
            turnover, tasks, today, sla_threshold_days=AGREEMENT_SLA_DAYS
        )
        priority = derive_priority_from_agreements(agreements)
        sort_key = urgency_sort_key(priority, turnover, today)

        item = {
            "turnover": {
                **turnover,
                "lifecycle_phase": phase,
                "days_since_move_out": days_out,
                "days_to_move_in": days_in,
                "vacancy_days": vac_days,
                "days_to_be_ready": dtbr,
                "effective_manual_ready_status": effective_manual_ready_status(turnover, today),
                "effective_availability_status": effective_availability_status(turnover, today),
            },
            "unit": unit,
            "tasks": tasks,
            "readiness": {
                "state": state,
                "completed": completed,
                "total": total,
                "blockers": blockers,
            },
            "sla": {
                "risk_level": risk_level,
                "days_until_breach": remaining,
                "move_in_pressure": pressure,
            },
            "agreements": agreements,
            "priority": priority,
            "risks": risks,
            "notes": notes,
            "_sort_key": sort_key,
        }
        board.append(item)

    board.sort(key=lambda item: item["_sort_key"])
    return board


def get_board_view(
    property_id: int,
    today: date | None = None,
    phase_scope: list[int] | None = None,
    sla_threshold: int = DEFAULT_SLA_THRESHOLD_DAYS,
    user_id: int = 0,
) -> list[dict]:
    """Single entry point for board data. Returns same structure as get_board.
    When phase_scope is None, resolves via scope_service.get_phase_scope(user_id, property_id)."""
    if phase_scope is None:
        phase_scope = scope_service.get_phase_scope(user_id, property_id)
    return get_board(
        property_id, today=today, sla_threshold=sla_threshold, phase_scope=phase_scope
    )


def work_stalled_unit_entries(board: list[dict]) -> list[dict]:
    """Board items that count toward work_stalled in get_board_metrics (shared rule)."""
    out: list[dict] = []
    for item in board:
        readiness_st = item["readiness"]["state"]
        dv = item["turnover"].get("days_since_move_out")
        if readiness_st in ("IN_PROGRESS", "NOT_STARTED") and dv is not None and dv > 5:
            unit = item.get("unit")
            code = unit["unit_code_norm"] if unit else "?"
            out.append(
                {
                    "unit_code": code,
                    "dv": dv,
                    "turnover_id": item["turnover"]["turnover_id"],
                }
            )
    return out


def get_board_summary(
    property_id: int,
    today: date | None = None,
    phase_scope: list[int] | None = None,
    board: list | None = None,
    user_id: int = 0,
) -> dict:
    """Return aggregate counts for the property board."""
    if board is None:
        if phase_scope is None:
            phase_scope = scope_service.get_phase_scope(user_id, property_id)
        board = get_board(property_id, today, phase_scope=phase_scope)

    by_priority = {}
    for level in PRIORITY_ORDER:
        by_priority[level] = 0
    for item in board:
        prio = item["priority"]
        by_priority[prio] = by_priority.get(prio, 0) + 1

    by_phase = {}
    for item in board:
        phase = item["turnover"]["lifecycle_phase"]
        by_phase[phase] = by_phase.get(phase, 0) + 1

    by_readiness = {}
    for item in board:
        state = item["readiness"]["state"]
        by_readiness[state] = by_readiness.get(state, 0) + 1

    return {
        "total": len(board),
        "by_priority": by_priority,
        "by_phase": by_phase,
        "by_readiness": by_readiness,
    }


def get_board_metrics(
    property_id: int | None = None,
    today: date | None = None,
    phase_scope: list[int] | None = None,
    board: list | None = None,
    user_id: int = 0,
) -> dict:
    """Return the six headline metrics for the board metrics bar."""
    if board is None:
        if phase_scope is None and property_id is not None:
            phase_scope = scope_service.get_phase_scope(user_id, property_id)
        board = get_board(property_id, today, phase_scope=phase_scope)
    active = len(board)
    violations = 0
    plan_breach = 0
    sla_breach = 0
    move_in_risk = 0

    for item in board:
        agreements = item.get("agreements")
        if agreements is not None:
            if agreements.get("viol") == "RED":
                violations += 1
            if agreements.get("plan") == "RED":
                plan_breach += 1
            if agreements.get("sla") == "RED":
                sla_breach += 1
            if agreements.get("move_in") == "RED":
                move_in_risk += 1
        else:
            priority = item["priority"]
            sla_level = item["sla"]["risk_level"]
            readiness_st = item["readiness"]["state"]
            pressure = item["sla"].get("move_in_pressure")
            if priority in ("MOVE_IN_DANGER", "SLA_RISK"):
                violations += 1
            if readiness_st == "BLOCKED" and priority not in ("MOVE_IN_DANGER", "SLA_RISK"):
                plan_breach += 1
            if sla_level in ("WARNING", "BREACH"):
                sla_breach += 1
            if pressure is not None and pressure <= 3:
                move_in_risk += 1
    work_stalled = len(work_stalled_unit_entries(board))

    return {
        "active": active,
        "violations": violations,
        "plan_breach": plan_breach,
        "sla_breach": sla_breach,
        "move_in_risk": move_in_risk,
        "work_stalled": work_stalled,
    }


def get_flag_counts(
    property_id: int,
    today: date | None = None,
    phase_scope: list[int] | None = None,
    board: list | None = None,
    user_id: int = 0,
) -> dict[str, int]:
    """Return counts per breach category for the sidebar Top Flags."""
    if board is None:
        if phase_scope is None:
            phase_scope = scope_service.get_phase_scope(user_id, property_id)
        board = get_board(property_id, today, phase_scope=phase_scope)
    counts: dict[str, int] = {
        "SLA_BREACH": 0,
        "MOVE_IN_DANGER": 0,
        "INSPECTION_BREACH": 0,
        "PLAN_BLOCKED": 0,
    }
    for item in board:
        agreements = item.get("agreements")
        if agreements is not None:
            if agreements.get("move_in") == "RED":
                counts["MOVE_IN_DANGER"] += 1
            if agreements.get("sla") == "RED":
                counts["SLA_BREACH"] += 1
            if agreements.get("inspection") == "RED":
                counts["INSPECTION_BREACH"] += 1
            if agreements.get("plan") == "RED":
                counts["PLAN_BLOCKED"] += 1
        else:
            priority = item["priority"]
            sla_level = item["sla"]["risk_level"]
            readiness_state = item["readiness"]["state"]
            if priority == "MOVE_IN_DANGER":
                counts["MOVE_IN_DANGER"] += 1
            elif priority == "SLA_RISK" or sla_level in ("WARNING", "BREACH"):
                counts["SLA_BREACH"] += 1
            elif priority == "INSPECTION_DELAY":
                counts["INSPECTION_BREACH"] += 1
            if readiness_state == "BLOCKED" and priority not in ("MOVE_IN_DANGER", "SLA_RISK"):
                counts["PLAN_BLOCKED"] += 1

    return counts


def get_flag_units(
    property_id: int,
    today: date | None = None,
    phase_scope: list[int] | None = None,
    board: list | None = None,
    user_id: int = 0,
) -> dict[str, list[dict]]:
    """Return flagged units per breach category for the sidebar expanders.

    Each entry is a list of dicts with keys: unit_code, dv, turnover_id.
    """
    if board is None:
        if phase_scope is None:
            phase_scope = scope_service.get_phase_scope(user_id, property_id)
        board = get_board(property_id, today, phase_scope=phase_scope)
    cats: dict[str, list[dict]] = {
        "SLA_BREACH": [],
        "MOVE_IN_DANGER": [],
        "INSPECTION_BREACH": [],
        "PLAN_BLOCKED": [],
    }
    for item in board:
        agreements = item.get("agreements")
        unit = item.get("unit")
        code = unit["unit_code_norm"] if unit else "?"
        dv = item["turnover"].get("days_since_move_out", 0)
        phase_id = unit.get("phase_id") if unit else None
        entry = {"unit_code": code, "dv": dv, "turnover_id": item["turnover"]["turnover_id"], "phase_id": phase_id}

        if agreements is not None:
            if agreements.get("move_in") == "RED":
                cats["MOVE_IN_DANGER"].append(entry)
            if agreements.get("sla") == "RED":
                cats["SLA_BREACH"].append(entry)
            if agreements.get("inspection") == "RED":
                cats["INSPECTION_BREACH"].append(entry)
            if agreements.get("plan") == "RED":
                cats["PLAN_BLOCKED"].append(entry)
        else:
            priority = item["priority"]
            sla_level = item["sla"]["risk_level"]
            readiness_state = item["readiness"]["state"]
            if priority == "MOVE_IN_DANGER":
                cats["MOVE_IN_DANGER"].append(entry)
            elif priority == "SLA_RISK" or sla_level in ("WARNING", "BREACH"):
                cats["SLA_BREACH"].append(entry)
            elif priority == "INSPECTION_DELAY":
                cats["INSPECTION_BREACH"].append(entry)
            if readiness_state == "BLOCKED" and priority not in ("MOVE_IN_DANGER", "SLA_RISK"):
                cats["PLAN_BLOCKED"].append(entry)

    return cats


def get_morning_risk_metrics(
    property_id: int,
    today: date | None = None,
    phase_scope: list[int] | None = None,
    user_id: int = 0,
) -> dict:
    """Return the three risk-summary metrics for the Morning Workflow."""
    today = today or date.today()
    if phase_scope is None:
        phase_scope = scope_service.get_phase_scope(user_id, property_id)
    board = get_board(property_id, today, phase_scope=phase_scope)
    vacant_over_7 = 0
    sla_breach = 0
    move_in_soon = 0
    for item in board:
        dv = item["turnover"].get("days_since_move_out")
        if dv is not None and dv > 7:
            vacant_over_7 += 1
        sla_level = item["sla"]["risk_level"]
        if sla_level in ("WARNING", "BREACH"):
            sla_breach += 1
        pressure = item["sla"].get("move_in_pressure")
        if pressure is not None and pressure <= 3:
            move_in_soon += 1
    return {
        "vacant_over_7": vacant_over_7,
        "sla_breach": sla_breach,
        "move_in_soon": move_in_soon,
    }


def get_todays_critical_units(
    property_id: int,
    today: date | None = None,
    phase_scope: list[int] | None = None,
    user_id: int = 0,
) -> list[dict]:
    """Return units with move-out, move-in, or ready dates matching today."""
    today = today or date.today()
    if phase_scope is None:
        phase_scope = scope_service.get_phase_scope(user_id, property_id)
    board = get_board(property_id, today, phase_scope=phase_scope)
    critical: list[dict] = []
    for item in board:
        turnover = item["turnover"]
        unit = item.get("unit")
        code = unit["unit_code_norm"] if unit else "?"
        tid = turnover["turnover_id"]
        mo = turnover.get("move_out_date")
        mi = turnover.get("move_in_date")
        if mo == today:
            critical.append({"unit_code": code, "event": "Move-Out", "date": "Today", "turnover_id": tid})
        if mi == today:
            critical.append({"unit_code": code, "event": "Move-In", "date": "Today", "turnover_id": tid})
    return critical


def filter_by_flag_category(board: list[dict], category: str) -> list[dict]:
    """Filter board items to those matching a breach category key. Uses agreements when present (Phase 4)."""
    result = []
    for item in board:
        agreements = item.get("agreements")
        if agreements is not None:
            if category == "MOVE_IN_DANGER" and agreements.get("move_in") == "RED":
                result.append(item)
            elif category == "SLA_RISK" and agreements.get("sla") == "RED":
                result.append(item)
            elif category == "INSPECTION_DELAY" and agreements.get("inspection") == "RED":
                result.append(item)
            elif category == "PLAN_BREACH" and agreements.get("plan") == "RED":
                result.append(item)
        else:
            priority = item["priority"]
            sla_level = item["sla"]["risk_level"]
            readiness_state = item["readiness"]["state"]
            if category == "MOVE_IN_DANGER" and priority == "MOVE_IN_DANGER":
                result.append(item)
            elif category == "SLA_RISK" and (priority == "SLA_RISK" or sla_level in ("WARNING", "BREACH")):
                result.append(item)
            elif category == "INSPECTION_DELAY" and priority == "INSPECTION_DELAY":
                result.append(item)
            elif category == "PLAN_BREACH" and readiness_state == "BLOCKED" and priority not in ("MOVE_IN_DANGER", "SLA_RISK"):
                result.append(item)
    return result


def has_any_breach(item: dict) -> bool:
    """True if board item has any breach. Uses agreement flags when present (Phase 4)."""
    agreements = item.get("agreements")
    if agreements is not None:
        return (
            agreements.get("inspection") == "RED"
            or agreements.get("sla") == "RED"
            or agreements.get("move_in") == "RED"
            or agreements.get("plan") == "RED"
            or agreements.get("viol") == "RED"
        )
    # Fallback when agreements missing (e.g. tests with synthetic items)
    priority = item["priority"]
    sla_level = item["sla"]["risk_level"]
    readiness_st = item["readiness"]["state"]
    pressure = item["sla"].get("move_in_pressure")
    if priority == "MOVE_IN_DANGER":
        return True
    if priority == "INSPECTION_DELAY":
        return True
    if priority == "SLA_RISK" or sla_level in ("WARNING", "BREACH"):
        return True
    if pressure is not None and pressure <= 3:
        return True
    if readiness_st == "BLOCKED" and priority not in ("MOVE_IN_DANGER", "SLA_RISK"):
        return True
    return False


def get_flag_bridge_metrics(board: list[dict]) -> dict:
    """Return Total Units, Violations, Units w/ Breach for a (possibly filtered) board list.
    Uses agreement flags when present (Phase 4)."""
    total = len(board)
    violations = 0
    for item in board:
        agreements = item.get("agreements")
        if agreements is not None:
            if agreements.get("viol") == "RED":
                violations += 1
        else:
            if item["priority"] in ("MOVE_IN_DANGER", "SLA_RISK"):
                violations += 1
    units_with_breach = sum(1 for item in board if has_any_breach(item))
    return {
        "total": total,
        "violations": violations,
        "units_with_breach": units_with_breach,
    }

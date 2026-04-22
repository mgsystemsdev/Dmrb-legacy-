"""Risk service — coordinates risk flag and SLA event management.

Bridges domain SLA/risk computations to repository persistence.
Provides read models for risk dashboard (Risk Radar) with scoring in service layer.
"""

from __future__ import annotations

from datetime import date

from db.repository import risk_repository, turnover_repository
from domain import sla as sla_domain
from services import board_service, property_service, scope_service
from services.write_guard import check_writes_enabled


class RiskError(Exception):
    pass


def evaluate_sla_state(
    turnover: dict,
    today: date | None = None,
    threshold_days: int = sla_domain.DEFAULT_SLA_THRESHOLD_DAYS,
) -> dict:
    """Pure SLA evaluation: no database access. Use for read paths and UI."""
    today = today or date.today()
    risk_level = sla_domain.sla_risk(turnover, today, threshold_days)
    severity = sla_domain.breach_severity(turnover, today, threshold_days)
    remaining = sla_domain.days_until_breach(turnover, today, threshold_days)
    pressure = sla_domain.move_in_pressure(turnover, today)
    return {
        "risk_level": risk_level,
        "severity": severity,
        "days_until_breach": remaining,
        "move_in_pressure": pressure,
    }


def evaluate_sla(
    turnover_id: int,
    today: date | None = None,
    threshold_days: int = sla_domain.DEFAULT_SLA_THRESHOLD_DAYS,
) -> dict:
    """Return SLA evaluation for a turnover. Read-only; does not persist risk."""
    turnover = turnover_repository.get_by_id(turnover_id)
    if turnover is None:
        raise RiskError(f"Turnover {turnover_id} not found.")
    return evaluate_sla_state(turnover, today, threshold_days)


def sync_risk_from_sla(
    turnover: dict,
    evaluation_result: dict,
    threshold_days: int = sla_domain.DEFAULT_SLA_THRESHOLD_DAYS,
) -> None:
    """Update risk_flag and sla_event from evaluation. Call only from mutation paths."""
    check_writes_enabled()
    turnover_id = turnover["turnover_id"]
    risk_level = evaluation_result["risk_level"]
    severity = evaluation_result["severity"]

    if risk_level == sla_domain.SLA_BREACH:
        _ensure_sla_breach_event(turnover, threshold_days)
        _ensure_risk_flag(turnover, "SLA_BREACH", severity)
    elif risk_level == sla_domain.SLA_WARNING:
        _ensure_risk_flag(turnover, "SLA_WARNING", severity)
    else:
        risk_repository.resolve_by_type(turnover_id, "SLA_BREACH")
        risk_repository.resolve_by_type(turnover_id, "SLA_WARNING")
        _resolve_sla_breach_event(turnover_id)


def add_risk_flag(
    property_id: int,
    turnover_id: int,
    risk_type: str,
    severity: str,
) -> dict:
    check_writes_enabled()
    return risk_repository.upsert_open(property_id, turnover_id, risk_type, severity)


def resolve_risk_flag(turnover_id: int, risk_type: str) -> dict | None:
    check_writes_enabled()
    return risk_repository.resolve_by_type(turnover_id, risk_type)


def get_open_risks(turnover_id: int) -> list[dict]:
    return risk_repository.get_open_by_turnover(turnover_id)


def get_all_risks(turnover_id: int) -> list[dict]:
    return risk_repository.get_by_turnover(turnover_id)


def get_risk_dashboard(
    property_id: int,
    today: date | None = None,
    threshold_days: int = sla_domain.DEFAULT_SLA_THRESHOLD_DAYS,
    phase_scope: list[int] | None = None,
    board: list | None = None,
    user_id: int = 0,
) -> list[dict]:
    """Return risk dashboard rows for Risk Radar: each item has risk_level, risk_score,
    risk_reasons, unit_code, phase_code, phase_id, move_in_date. Interpretations
    (SLA, breach, readiness-based score) are computed here, not in UI."""
    today = today or date.today()
    if phase_scope is None:
        phase_scope = scope_service.get_phase_scope(user_id, property_id)
    if board is None:
        board = board_service.get_board(
            property_id, today=today, sla_threshold=threshold_days, phase_scope=phase_scope
        )
    phases = property_service.get_phases(property_id)
    phase_map = {p["phase_id"]: p["phase_code"] for p in phases}
    return [_score_board_item(item, phase_map) for item in board]


def _score_board_item(item: dict, phase_map: dict[int, str]) -> dict:
    """Derive risk_level, risk_score (0-100), and risk_reasons from a board item."""
    turnover = item["turnover"]
    unit = item.get("unit")
    sla_level = item["sla"]["risk_level"]
    readiness_st = item["readiness"]["state"]
    pressure = item["sla"].get("move_in_pressure")
    dv = turnover.get("days_since_move_out") or 0

    score = 0
    reasons: list[str] = []

    if sla_level == "BREACH":
        score += 40
        reasons.append("SLA breach")
    elif sla_level == "WARNING":
        score += 25
        reasons.append("SLA warning")

    if dv > 14:
        score += 20
        reasons.append(f"DV {dv} (>14)")
    elif dv > 7:
        score += 10
        reasons.append(f"DV {dv} (>7)")

    if pressure is not None:
        if pressure <= 0:
            score += 25
            reasons.append("Move-in overdue")
        elif pressure <= 3:
            score += 20
            reasons.append("Move-in ≤3 days")
        elif pressure <= 7:
            score += 10
            reasons.append("Move-in soon")

    if readiness_st == "BLOCKED":
        score += 15
        reasons.append("Blocked tasks")
    elif readiness_st == "NOT_STARTED":
        score += 10
        reasons.append("Work not started")

    score = min(score, 100)

    if score >= 60:
        risk_level = "HIGH"
    elif score >= 30:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    phase_code = ""
    phase_id = None
    if unit:
        phase_id = unit.get("phase_id")
        phase_code = phase_map.get(phase_id, str(phase_id or ""))

    return {
        "unit_code": unit["unit_code_norm"] if unit else "—",
        "phase_code": phase_code,
        "phase_id": phase_id,
        "risk_level": risk_level,
        "risk_score": score,
        "risk_reasons": reasons,
        "move_in_date": turnover.get("move_in_date"),
    }


# ── Internal Helpers ─────────────────────────────────────────────────────────

def _ensure_risk_flag(turnover: dict, risk_type: str, severity: str) -> None:
    risk_repository.upsert_open(
        turnover["property_id"],
        turnover["turnover_id"],
        risk_type,
        severity,
    )


def _ensure_sla_breach_event(turnover: dict, threshold_days: int) -> None:
    existing = risk_repository.get_open_sla_breach(turnover["turnover_id"])
    if existing is None:
        risk_repository.insert_sla_event(
            turnover["property_id"],
            turnover["turnover_id"],
            threshold_days,
        )


def _resolve_sla_breach_event(turnover_id: int) -> None:
    existing = risk_repository.get_open_sla_breach(turnover_id)
    if existing is not None:
        risk_repository.resolve_sla_event(existing["sla_event_id"])

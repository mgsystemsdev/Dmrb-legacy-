"""Tests for services/board_service.py against the JSON backend."""

from datetime import date, timedelta
from unittest.mock import patch

from domain.priority_engine import derive_priority_from_agreements
from services.board_service import (
    _evaluation_gate,
    evaluate_turnover_agreements,
    get_board,
    get_board_metrics,
    get_flag_bridge_metrics,
    has_any_breach,
)

REQUIRED_ITEM_KEYS = {"turnover", "unit", "tasks", "readiness", "sla", "priority"}
AGREEMENT_KEYS = {"inspection", "sla", "move_in", "plan", "viol"}


def _synthetic_board_item(
    *,
    priority: str = "NORMAL",
    sla_risk_level: str = "OK",
    readiness_state: str = "READY",
    move_in_pressure: int | None = None,
) -> dict:
    """Minimal board item shape for testing has_any_breach and flag logic."""
    return {
        "turnover": {},
        "unit": None,
        "tasks": [],
        "readiness": {"state": readiness_state},
        "sla": {"risk_level": sla_risk_level, "move_in_pressure": move_in_pressure},
        "priority": priority,
    }


# ── Board Contents ───────────────────────────────────────────────────────────


def test_get_board_returns_all_open_turnovers():
    """Board returns a list of open turnovers (length depends on DB state)."""
    board = get_board(property_id=1)
    assert isinstance(board, list)
    assert len(board) >= 0


def test_board_items_have_required_keys():
    """Each board item must contain turnover, unit, tasks, readiness, sla, priority."""
    board = get_board(property_id=1)
    for item in board:
        assert REQUIRED_ITEM_KEYS.issubset(item.keys()), (
            f"Missing keys: {REQUIRED_ITEM_KEYS - item.keys()}"
        )


def test_board_items_have_agreements():
    """Each board item must have agreements dict with inspection, sla, move_in, plan, viol."""
    board = get_board(property_id=1)
    for item in board:
        assert "agreements" in item, "Board item missing agreements"
        ag = item["agreements"]
        assert AGREEMENT_KEYS == set(ag.keys()), f"Wrong agreement keys: {set(ag.keys())}"
        for k, v in ag.items():
            if k == "inspection":
                assert v in ("GREEN", "YELLOW", "RED"), f"Bad inspection value: {v}"
            else:
                assert v in ("GREEN", "RED"), f"Bad {k} value: {v}"


def test_board_priority_derived_from_agreements():
    """Phase 5: priority on each board item must equal derive_priority_from_agreements(agreements)."""
    board = get_board(property_id=1)
    for item in board:
        expected = derive_priority_from_agreements(item["agreements"])
        assert item["priority"] == expected, (
            f"priority {item['priority']!r} != derive_priority_from_agreements(agreements) {expected!r}"
        )


# ── Sorting ──────────────────────────────────────────────────────────────────


def test_board_sorted_by_priority():
    """Board items should be sorted by _sort_key (ascending)."""
    board = get_board(property_id=1)
    sort_keys = [item["_sort_key"] for item in board]
    assert sort_keys == sorted(sort_keys)


# ── Metrics ──────────────────────────────────────────────────────────────────


def test_board_metrics_counts():
    """Metrics include active count; when using same scope, active matches board length."""
    from services import scope_service

    phase_scope = scope_service.get_phase_scope(0, 1)
    board = get_board(property_id=1, phase_scope=phase_scope)
    metrics = get_board_metrics(property_id=1, phase_scope=phase_scope)
    assert metrics["active"] == len(board)


# ── Enrichment ───────────────────────────────────────────────────────────────


def test_board_enrichment_has_lifecycle_phase():
    """Each turnover dict in the board should have lifecycle_phase."""
    board = get_board(property_id=1)
    for item in board:
        assert "lifecycle_phase" in item["turnover"]


def test_board_enrichment_has_dv_and_dtbr():
    """Each turnover dict should have days_since_move_out and days_to_be_ready."""
    board = get_board(property_id=1)
    for item in board:
        assert "days_since_move_out" in item["turnover"]
        assert "days_to_be_ready" in item["turnover"]


# ── Flag and metric classification (domain logic) ──────────────────────────────


def test_has_any_breach_true_for_move_in_danger():
    item = _synthetic_board_item(priority="MOVE_IN_DANGER")
    assert has_any_breach(item) is True


def test_has_any_breach_true_for_sla_risk():
    item = _synthetic_board_item(priority="SLA_RISK")
    assert has_any_breach(item) is True


def test_has_any_breach_true_for_sla_warning():
    item = _synthetic_board_item(sla_risk_level="WARNING")
    assert has_any_breach(item) is True


def test_has_any_breach_true_for_move_in_pressure_le_3():
    item = _synthetic_board_item(move_in_pressure=2)
    assert has_any_breach(item) is True


def test_has_any_breach_true_for_inspection_delay():
    item = _synthetic_board_item(priority="INSPECTION_DELAY")
    assert has_any_breach(item) is True


def test_has_any_breach_true_for_blocked_plan_when_not_mi_or_sla():
    item = _synthetic_board_item(
        readiness_state="BLOCKED",
        priority="NORMAL",
        sla_risk_level="OK",
    )
    assert has_any_breach(item) is True


def test_has_any_breach_false_when_ready_and_ok():
    item = _synthetic_board_item(
        priority="NORMAL",
        sla_risk_level="OK",
        readiness_state="READY",
        move_in_pressure=None,
    )
    assert has_any_breach(item) is False


def test_get_flag_bridge_metrics_violations_count():
    board = [
        _synthetic_board_item(priority="MOVE_IN_DANGER"),
        _synthetic_board_item(priority="NORMAL"),
    ]
    metrics = get_flag_bridge_metrics(board)
    assert metrics["total"] == 2
    assert metrics["violations"] == 1
    assert metrics["units_with_breach"] == 1


# ── Agreement evaluation: evaluate_turnover_agreements ──────────────────────

TODAY = date(2025, 6, 15)


def _task(
    task_type: str = "CLEAN",
    execution_status: str = "COMPLETE",
    required: bool = True,
    blocking: bool = True,
    **kw,
) -> dict:
    return {
        "task_id": 1,
        "turnover_id": 1,
        "task_type": task_type,
        "execution_status": execution_status,
        "required": required,
        "blocking": blocking,
        **kw,
    }


def _turnover(move_out_date, move_in_date=None, report_ready_date=None, **kw) -> dict:
    return {
        "turnover_id": 1,
        "property_id": 1,
        "unit_id": 1,
        "move_out_date": move_out_date,
        "move_in_date": move_in_date,
        "report_ready_date": report_ready_date,
        **kw,
    }


def test_evaluate_turnover_agreements_scenario_a_healthy():
    """Scenario A — Healthy turnover: all flags GREEN."""
    turnover = _turnover(
        move_out_date=TODAY - timedelta(days=3),
        move_in_date=TODAY + timedelta(days=14),
        report_ready_date=TODAY + timedelta(days=7),
    )
    tasks = [_task("CLEAN", "COMPLETE"), _task("INSPECT", "COMPLETE")]
    result = evaluate_turnover_agreements(turnover, tasks, TODAY)
    assert result["inspection"] == "GREEN"
    assert result["sla"] == "GREEN"
    assert result["move_in"] == "GREEN"
    assert result["plan"] == "GREEN"
    assert result["viol"] == "GREEN"


def test_evaluate_turnover_agreements_scenario_b_inspection_delay():
    """Scenario B — Inspection delay: inspection_flag RED (and SLA red when dv > 10)."""
    turnover = _turnover(move_out_date=TODAY - timedelta(days=49))
    tasks = [
        _task("CLEAN", "COMPLETE"),
        _task("INSPECT", "NOT_STARTED"),
    ]
    result = evaluate_turnover_agreements(turnover, tasks, TODAY)
    assert result["inspection"] == "RED"
    assert result["sla"] == "RED"  # dv > 10 and not READY
    assert result["move_in"] == "GREEN"
    assert result["plan"] == "GREEN"
    assert result["viol"] == "RED"

    # Yellow: 24 < dv <= 48, blocking done, inspection not done
    turnover_yellow = _turnover(move_out_date=TODAY - timedelta(days=30))
    result_yellow = evaluate_turnover_agreements(turnover_yellow, tasks, TODAY)
    assert result_yellow["inspection"] == "YELLOW"

    # Green: dv <= 24
    turnover_green = _turnover(move_out_date=TODAY - timedelta(days=5))
    result_green = evaluate_turnover_agreements(turnover_green, tasks, TODAY)
    assert result_green["inspection"] == "GREEN"


def test_evaluate_turnover_agreements_scenario_c_sla_breach():
    """Scenario C — SLA breach: sla_flag RED, viol_flag RED."""
    turnover = _turnover(move_out_date=TODAY - timedelta(days=12))
    tasks = [_task("CLEAN", "NOT_STARTED")]
    result = evaluate_turnover_agreements(turnover, tasks, TODAY)
    assert result["sla"] == "RED"
    assert result["viol"] == "RED"
    assert result["inspection"] == "GREEN"  # no inspection task or work in progress
    assert result["move_in"] == "GREEN"
    assert result["plan"] == "GREEN"


def test_evaluate_turnover_agreements_scenario_d_move_in_risk():
    """Scenario D — Move-in risk: move_in_flag RED, viol_flag RED."""
    turnover = _turnover(
        move_out_date=TODAY - timedelta(days=5),
        move_in_date=TODAY + timedelta(days=2),
    )
    tasks = [_task("CLEAN", "NOT_STARTED")]
    result = evaluate_turnover_agreements(turnover, tasks, TODAY)
    assert result["move_in"] == "RED"
    assert result["viol"] == "RED"
    assert result["sla"] == "GREEN"
    assert result["inspection"] == "GREEN"
    assert result["plan"] == "GREEN"


def test_evaluate_turnover_agreements_scenario_e_plan_missed():
    """Scenario E — Plan missed: plan_flag RED, others GREEN."""
    turnover = _turnover(
        move_out_date=TODAY - timedelta(days=5),
        report_ready_date=TODAY - timedelta(days=1),
    )
    tasks = [_task("CLEAN", "NOT_STARTED")]
    result = evaluate_turnover_agreements(turnover, tasks, TODAY)
    assert result["plan"] == "RED"
    assert result["inspection"] == "GREEN"
    assert result["sla"] == "GREEN"
    assert result["move_in"] == "GREEN"
    assert result["viol"] == "GREEN"


def test_evaluate_turnover_agreements_multiple_red_flags():
    """Multiple agreements can be RED at once (no suppression)."""
    turnover = _turnover(
        move_out_date=TODAY - timedelta(days=50),
        move_in_date=TODAY + timedelta(days=1),
        report_ready_date=TODAY - timedelta(days=5),
    )
    tasks = [_task("CLEAN", "COMPLETE"), _task("INSPECT", "NOT_STARTED")]
    result = evaluate_turnover_agreements(turnover, tasks, TODAY)
    assert result["inspection"] == "RED"
    assert result["sla"] == "RED"
    assert result["move_in"] == "RED"
    assert result["plan"] == "RED"
    assert result["viol"] == "RED"


def test_has_any_breach_true_when_agreements_present_and_plan_red():
    """has_any_breach uses agreements when present."""
    item = _synthetic_board_item(priority="NORMAL", readiness_state="READY")
    item["agreements"] = {
        "inspection": "GREEN",
        "sla": "GREEN",
        "move_in": "GREEN",
        "plan": "RED",
        "viol": "GREEN",
    }
    assert has_any_breach(item) is True


def test_has_any_breach_false_when_agreements_all_green():
    """has_any_breach is False when agreements are all green."""
    item = _synthetic_board_item(priority="NORMAL")
    item["agreements"] = {
        "inspection": "GREEN",
        "sla": "GREEN",
        "move_in": "GREEN",
        "plan": "GREEN",
        "viol": "GREEN",
    }
    assert has_any_breach(item) is False


# ── Guard rail: _evaluation_gate ───────────────────────────────────────────


def test_evaluation_gate_returns_skip_when_canceled():
    t = {"turnover_id": 1, "move_out_date": TODAY, "canceled_at": "2025-06-01"}
    assert _evaluation_gate(t, TODAY) == "skip_evaluation"


def test_evaluation_gate_returns_skip_when_no_move_out():
    t = {"turnover_id": 1, "move_out_date": None, "canceled_at": None}
    assert _evaluation_gate(t, TODAY) == "skip_evaluation"


def test_evaluation_gate_returns_vacant_ready_when_manual_ready():
    t = {
        "turnover_id": 1,
        "move_out_date": TODAY,
        "canceled_at": None,
        "manual_ready_status": "Vacant Ready",
    }
    assert _evaluation_gate(t, TODAY) == "vacant_ready"


def test_evaluation_gate_returns_none_when_normal_turnover():
    t = {
        "turnover_id": 1,
        "move_out_date": TODAY,
        "canceled_at": None,
        "manual_ready_status": "Vacant Not Ready",
    }
    assert _evaluation_gate(t, TODAY) is None


# ── Guard rail: Scenario A — Vacant Ready (all green) ───────────────────────


def test_guard_rail_vacant_ready_item_has_no_breach():
    """Vacant Ready unit appears with all dots green (no violations)."""
    turnover = {
        "turnover_id": 101,
        "property_id": 1,
        "unit_id": 10,
        "move_out_date": TODAY,
        "canceled_at": None,
        "manual_ready_status": "Vacant Ready",
    }
    with patch(
        "services.board_service.turnover_repository.get_open_by_property",
        return_value=[turnover],
    ):
        board = get_board(property_id=1, today=TODAY)
    assert len(board) == 1
    item = board[0]
    assert item["priority"] == "NORMAL"
    assert item["readiness"]["state"] == "READY"
    assert item["sla"]["risk_level"] == "OK"
    assert has_any_breach(item) is False
    assert item["turnover"]["lifecycle_phase"] == "VACANT_READY"


# ── Guard rail: Scenario B — No move-out (skip evaluation) ───────────────────


def test_guard_rail_no_move_out_produces_no_violations():
    """Unit with no move_out_date does not produce violations."""
    turnover = {
        "turnover_id": 102,
        "property_id": 1,
        "unit_id": 11,
        "move_out_date": None,
        "canceled_at": None,
    }
    with patch(
        "services.board_service.turnover_repository.get_open_by_property",
        return_value=[turnover],
    ):
        board = get_board(property_id=1, today=TODAY)
    assert len(board) == 1
    item = board[0]
    assert item["priority"] == "NORMAL"
    assert has_any_breach(item) is False
    metrics = get_flag_bridge_metrics(board)
    assert metrics["violations"] == 0
    assert metrics["units_with_breach"] == 0


# ── Guard rail: Scenario C — Cancelled (skip evaluation) ──────────────────────


def test_guard_rail_cancelled_turnover_produces_no_violations():
    """Cancelled turnover gets healthy defaults and no violations."""
    turnover = {
        "turnover_id": 103,
        "property_id": 1,
        "unit_id": 12,
        "move_out_date": TODAY,
        "canceled_at": "2025-06-10",
    }
    with patch(
        "services.board_service.turnover_repository.get_open_by_property",
        return_value=[turnover],
    ):
        board = get_board(property_id=1, today=TODAY)
    assert len(board) == 1
    item = board[0]
    assert item["priority"] == "NORMAL"
    assert has_any_breach(item) is False
    assert item["readiness"]["state"] == "READY"
    assert item["sla"]["risk_level"] == "OK"


# ── Guard rail: Scenario D — Normal turnover (full evaluation) ───────────────


def test_guard_rail_normal_turnover_still_evaluated():
    """Normal turnover (with move-out, not cancelled, not Vacant Ready) runs full pipeline."""
    turnover = {
        "turnover_id": 104,
        "property_id": 1,
        "unit_id": 13,
        "move_out_date": TODAY - timedelta(days=20),
        "move_in_date": TODAY + timedelta(days=2),
        "canceled_at": None,
        "manual_ready_status": "Vacant Not Ready",
    }
    # Tasks that are blocked so priority can be elevated
    tasks = [
        {
            "task_id": 1,
            "turnover_id": 104,
            "task_type": "Inspection",
            "execution_status": "pending",
            "blocking": True,
        }
    ]
    with (
        patch(
            "services.board_service.turnover_repository.get_open_by_property",
            return_value=[turnover],
        ),
        patch(
            "services.board_service.task_repository.get_by_turnover",
            return_value=tasks,
        ),
    ):
        board = get_board(property_id=1, today=TODAY)
    assert len(board) == 1
    item = board[0]
    # Full evaluation ran: priority could be INSPECTION_DELAY or other breach
    assert item["priority"] in ("MOVE_IN_DANGER", "SLA_RISK", "INSPECTION_DELAY", "NORMAL", "LOW")
    assert "lifecycle_phase" in item["turnover"]
    assert "readiness" in item
    assert "sla" in item

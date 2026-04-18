"""Tests for domain.priority_engine — operational priority computation."""

from __future__ import annotations

from datetime import date, timedelta

from domain.priority_engine import (
    INSPECTION_DELAY,
    LOW,
    MOVE_IN_DANGER,
    NORMAL,
    PLAN_DELAY,
    PRIORITY_ORDER,
    SLA_RISK_LEVEL,
    derive_priority_from_agreements,
    priority_level,
    priority_sort_key,
    urgency_sort_key,
)

TODAY = date(2025, 6, 15)


def _turnover(move_out_date, **kw):
    return {
        "turnover_id": 1,
        "property_id": 1,
        "unit_id": 1,
        "move_out_date": move_out_date,
        "move_in_date": None,
        "closed_at": None,
        "canceled_at": None,
        "manual_ready_status": None,
        **kw,
    }


def _task(
    task_type="PAINT",
    execution_status="NOT_STARTED",
    required=True,
    blocking=True,
    **kw,
):
    return {
        "task_id": 1,
        "task_type": task_type,
        "execution_status": execution_status,
        "required": required,
        "blocking": blocking,
        "vendor_completed_at": None,
        **kw,
    }


class TestPriorityLevel:
    def test_closed_turnover_is_low(self):
        t = _turnover(TODAY - timedelta(days=5), closed_at="2025-06-10")
        assert priority_level(t, [], today=TODAY) == LOW

    def test_move_in_danger_when_imminent_and_not_ready(self):
        t = _turnover(
            TODAY - timedelta(days=10),
            move_in_date=TODAY + timedelta(days=2),
        )
        tasks = [_task(execution_status="SCHEDULED")]
        assert priority_level(t, tasks, today=TODAY) == MOVE_IN_DANGER

    def test_sla_risk_when_breaching(self):
        # move_out 14 days ago → SLA BREACH, no imminent move-in
        t = _turnover(TODAY - timedelta(days=14))
        tasks = [_task(execution_status="SCHEDULED")]
        assert priority_level(t, tasks, today=TODAY, sla_threshold=14) == SLA_RISK_LEVEL

    def test_inspection_delay_when_blocked(self):
        # move_out recent (within SLA OK window), tasks are BLOCKED
        t = _turnover(TODAY - timedelta(days=3))
        tasks = [
            _task(execution_status="COMPLETED"),
            _task(task_type="CLEAN", execution_status="SCHEDULED"),
            _task(task_type="INSPECT", execution_status="NOT_STARTED"),
        ]
        assert priority_level(t, tasks, today=TODAY) == INSPECTION_DELAY

    def test_normal_progress(self):
        # Vacant not ready, tasks in progress but not blocked, SLA OK
        t = _turnover(TODAY - timedelta(days=3))
        tasks = [
            _task(execution_status="SCHEDULED", blocking=False),
            _task(task_type="CLEAN", execution_status="SCHEDULED", blocking=False),
        ]
        assert priority_level(t, tasks, today=TODAY) == NORMAL

    def test_low_when_ready(self):
        t = _turnover(
            TODAY - timedelta(days=5),
            manual_ready_status="Vacant Ready",
        )
        tasks = [_task(execution_status="COMPLETED")]
        assert priority_level(t, tasks, today=TODAY) == LOW


class TestPrioritySortKey:
    def test_move_in_unit_sorts_before_no_move_in(self):
        t_mi = _turnover(TODAY - timedelta(days=5), move_in_date=TODAY + timedelta(days=10))
        t_no = _turnover(TODAY - timedelta(days=30))
        assert priority_sort_key(t_mi, [], today=TODAY) < priority_sort_key(t_no, [], today=TODAY)

    def test_higher_dv_sorts_first_when_no_move_in(self):
        t_old = _turnover(TODAY - timedelta(days=30))
        t_new = _turnover(TODAY - timedelta(days=3))
        assert priority_sort_key(t_old, [], today=TODAY) < priority_sort_key(t_new, [], today=TODAY)

    def test_delegates_to_urgency_sort_key(self):
        t = _turnover(TODAY - timedelta(days=5))
        psk = priority_sort_key(t, [], today=TODAY)
        usk = urgency_sort_key(NORMAL, t, today=TODAY)
        assert psk == usk


class TestCrossFunctionConsistency:
    """Priority depends on readiness and SLA; changes in one update the other."""

    def test_readiness_blocked_to_ready_changes_priority(self):
        t = _turnover(TODAY - timedelta(days=3))
        tasks_blocked = [
            _task(execution_status="COMPLETED"),
            _task(task_type="CLEAN", execution_status="SCHEDULED"),
            _task(task_type="INSPECT", execution_status="NOT_STARTED"),
        ]
        tasks_ready = [
            _task(execution_status="COMPLETED"),
            _task(task_type="CLEAN", execution_status="COMPLETED"),
            _task(task_type="INSPECT", execution_status="COMPLETED"),
        ]
        assert priority_level(t, tasks_blocked, today=TODAY) == INSPECTION_DELAY
        assert priority_level(t, tasks_ready, today=TODAY) == NORMAL

    def test_sla_breach_elevates_priority_to_sla_risk(self):
        t = _turnover(TODAY - timedelta(days=14))
        tasks = [_task(execution_status="SCHEDULED")]
        assert priority_level(t, tasks, today=TODAY, sla_threshold=14) == SLA_RISK_LEVEL


class TestFailureDetection:
    """Priority must not be NORMAL when SLA is BREACH (open turnover)."""

    def test_priority_not_normal_when_sla_breach(self):
        t = _turnover(TODAY - timedelta(days=20))
        tasks = [_task(execution_status="IN_PROGRESS")]
        level = priority_level(t, tasks, today=TODAY, sla_threshold=14)
        assert level != NORMAL
        assert level == SLA_RISK_LEVEL


# ── Phase 5: derive_priority_from_agreements ─────────────────────────────────


class TestDerivePriorityFromAgreements:
    """Priority is derived from agreement flags only (severity order)."""

    def test_case_1_move_in_red_returns_move_in_danger(self):
        agreements = {
            "inspection": "GREEN",
            "sla": "GREEN",
            "move_in": "RED",
            "plan": "GREEN",
            "viol": "RED",
        }
        assert derive_priority_from_agreements(agreements) == MOVE_IN_DANGER

    def test_case_2_sla_red_returns_sla_risk(self):
        agreements = {
            "inspection": "GREEN",
            "sla": "RED",
            "move_in": "GREEN",
            "plan": "GREEN",
            "viol": "RED",
        }
        assert derive_priority_from_agreements(agreements) == SLA_RISK_LEVEL

    def test_case_3_inspection_red_returns_inspection_delay(self):
        agreements = {
            "inspection": "RED",
            "sla": "GREEN",
            "move_in": "GREEN",
            "plan": "GREEN",
            "viol": "GREEN",
        }
        assert derive_priority_from_agreements(agreements) == INSPECTION_DELAY

    def test_case_4_plan_red_returns_plan_delay(self):
        agreements = {
            "inspection": "GREEN",
            "sla": "GREEN",
            "move_in": "GREEN",
            "plan": "RED",
            "viol": "GREEN",
        }
        assert derive_priority_from_agreements(agreements) == PLAN_DELAY

    def test_case_5_all_green_returns_normal(self):
        agreements = {
            "inspection": "GREEN",
            "sla": "GREEN",
            "move_in": "GREEN",
            "plan": "GREEN",
            "viol": "GREEN",
        }
        assert derive_priority_from_agreements(agreements) == NORMAL

    def test_severity_order_move_in_beats_sla(self):
        agreements = {
            "inspection": "RED",
            "sla": "RED",
            "move_in": "RED",
            "plan": "RED",
            "viol": "RED",
        }
        assert derive_priority_from_agreements(agreements) == MOVE_IN_DANGER

    def test_severity_order_sla_beats_inspection(self):
        agreements = {
            "inspection": "RED",
            "sla": "RED",
            "move_in": "GREEN",
            "plan": "GREEN",
            "viol": "RED",
        }
        assert derive_priority_from_agreements(agreements) == SLA_RISK_LEVEL


class TestUrgencySortKey:
    """Sort key: move-in units first (closest first), then DV descending."""

    def test_move_in_sorts_before_no_move_in(self):
        t_mi = _turnover(TODAY - timedelta(days=5), move_in_date=TODAY + timedelta(days=10))
        t_no = _turnover(TODAY - timedelta(days=30))
        assert urgency_sort_key(NORMAL, t_mi, today=TODAY) < urgency_sort_key(NORMAL, t_no, today=TODAY)

    def test_closer_move_in_sorts_first(self):
        t_soon = _turnover(TODAY - timedelta(days=5), move_in_date=TODAY + timedelta(days=3))
        t_later = _turnover(TODAY - timedelta(days=5), move_in_date=TODAY + timedelta(days=20))
        assert urgency_sort_key(NORMAL, t_soon, today=TODAY) < urgency_sort_key(NORMAL, t_later, today=TODAY)

    def test_higher_dv_sorts_first_when_no_move_in(self):
        t_old = _turnover(TODAY - timedelta(days=30))
        t_new = _turnover(TODAY - timedelta(days=5))
        assert urgency_sort_key(NORMAL, t_old, today=TODAY) < urgency_sort_key(NORMAL, t_new, today=TODAY)

    def test_pre1990_sentinel_treated_as_no_move_in(self):
        t = _turnover(TODAY - timedelta(days=10), move_in_date=date(1900, 1, 1))
        assert urgency_sort_key(NORMAL, t, today=TODAY)[0] == 1

"""Boundary and edge case tests for domain logic (Step 3).

Ensures no crash and deterministic results for: no tasks, move_out None,
move_in None, future move-out, optional-only tasks, vendor_due_date None.
"""

from __future__ import annotations

from datetime import date, timedelta

from domain import readiness, sla, turnover_lifecycle
from domain.readiness import NO_TASKS, READY
from domain.turnover_lifecycle import PHASE_ON_NOTICE, PHASE_PRE_NOTICE

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
        **kw,
    }


def _task(execution_status="SCHEDULED", required=True, blocking=True, vendor_due_date=None, **kw):
    return {
        "task_id": 1,
        "task_type": "PAINT",
        "execution_status": execution_status,
        "required": required,
        "blocking": blocking,
        "vendor_due_date": vendor_due_date,
        **kw,
    }


class TestNoTasks:
    def test_readiness_no_tasks(self):
        assert readiness.readiness_state([]) == NO_TASKS

    def test_dtbr_no_tasks(self):
        t = _turnover(TODAY - timedelta(days=5))
        assert turnover_lifecycle.days_to_be_ready(t, [], today=TODAY) == 0

    def test_priority_no_tasks_depends_on_phase_and_sla(self):
        from domain.priority_engine import priority_level

        t = _turnover(TODAY + timedelta(days=5))
        level = priority_level(t, [], today=TODAY)
        assert level in ("LOW", "NORMAL", "SLA_RISK", "MOVE_IN_DANGER", "INSPECTION_DELAY")


class TestMoveOutNone:
    def test_days_since_move_out_none(self):
        t = _turnover(TODAY)
        t["move_out_date"] = None
        assert turnover_lifecycle.days_since_move_out(t, today=TODAY) is None

    def test_sla_risk_ok_when_move_out_none(self):
        t = _turnover(TODAY)
        t["move_out_date"] = None
        assert sla.sla_risk(t, today=TODAY) == sla.SLA_OK


class TestMoveInNone:
    def test_move_in_pressure_none(self):
        t = _turnover(TODAY - timedelta(days=5))
        assert turnover_lifecycle.days_to_move_in(t, today=TODAY) is None
        assert sla.move_in_pressure(t, today=TODAY) is None

    def test_dtbr_not_capped_when_no_move_in(self):
        t = _turnover(TODAY - timedelta(days=5))
        tasks = [_task(execution_status="SCHEDULED", vendor_due_date=TODAY + timedelta(days=10))]
        assert turnover_lifecycle.days_to_be_ready(t, tasks, today=TODAY) == 10


class TestFutureMoveOut:
    def test_lifecycle_pre_notice_or_on_notice(self):
        t = _turnover(TODAY + timedelta(days=10))
        phase = turnover_lifecycle.lifecycle_phase(t, today=TODAY)
        assert phase in (PHASE_PRE_NOTICE, PHASE_ON_NOTICE)

    def test_sla_ok_future_move_out(self):
        t = _turnover(TODAY + timedelta(days=5))
        assert sla.sla_risk(t, today=TODAY) == sla.SLA_OK


class TestAllOptionalTasks:
    def test_readiness_ready_when_no_required_blocking(self):
        tasks = [
            _task(required=False, blocking=False, execution_status="SCHEDULED"),
        ]
        assert readiness.readiness_state(tasks) == READY


class TestTasksWithVendorDueDateNone:
    def test_dtbr_excludes_tasks_without_due_date(self):
        t = _turnover(TODAY - timedelta(days=5))
        tasks = [
            _task(execution_status="SCHEDULED", vendor_due_date=None),
            _task(
                task_type="CLEAN",
                execution_status="SCHEDULED",
                vendor_due_date=TODAY + timedelta(days=3),
            ),
        ]
        assert turnover_lifecycle.days_to_be_ready(t, tasks, today=TODAY) == 3

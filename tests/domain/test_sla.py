"""Tests for domain.sla — SLA breach risk computation."""

from __future__ import annotations

from datetime import date, timedelta

from domain.sla import (
    SLA_BREACH,
    SLA_OK,
    SLA_WARNING,
    breach_severity,
    days_until_breach,
    move_in_pressure,
    sla_risk,
)

TODAY = date(2025, 6, 15)


def _turnover(move_out_date, **kw):
    return {
        "turnover_id": 1,
        "move_out_date": move_out_date,
        "move_in_date": None,
        "closed_at": None,
        "canceled_at": None,
        **kw,
    }


class TestSlaRisk:
    def test_ok_before_move_out(self):
        t = _turnover(TODAY + timedelta(days=5))
        assert sla_risk(t, today=TODAY, threshold_days=14) == SLA_OK

    def test_ok_early_vacancy(self):
        t = _turnover(TODAY - timedelta(days=5))
        assert sla_risk(t, today=TODAY, threshold_days=14) == SLA_OK

    def test_warning_threshold(self):
        # 75% of 14 = 10.5 → int = 10. elapsed=11 >= 10 → WARNING
        t = _turnover(TODAY - timedelta(days=11))
        assert sla_risk(t, today=TODAY, threshold_days=14) == SLA_WARNING

    def test_breach_at_threshold(self):
        t = _turnover(TODAY - timedelta(days=14))
        assert sla_risk(t, today=TODAY, threshold_days=14) == SLA_BREACH

    def test_closed_turnover_always_ok(self):
        t = _turnover(TODAY - timedelta(days=30), closed_at="2025-06-10")
        assert sla_risk(t, today=TODAY, threshold_days=14) == SLA_OK


class TestDaysUntilBreach:
    def test_days_until_breach(self):
        t = _turnover(TODAY - timedelta(days=5))
        assert days_until_breach(t, today=TODAY, threshold_days=14) == 9

    def test_days_until_breach_already_breached(self):
        t = _turnover(TODAY - timedelta(days=20))
        assert days_until_breach(t, today=TODAY, threshold_days=14) == -6

    def test_days_until_breach_closed_returns_none(self):
        t = _turnover(TODAY - timedelta(days=5), closed_at="2025-06-10")
        assert days_until_breach(t, today=TODAY) is None


class TestMoveInPressure:
    def test_move_in_pressure(self):
        t = _turnover(TODAY - timedelta(days=10), move_in_date=TODAY + timedelta(days=5))
        assert move_in_pressure(t, today=TODAY) == 5

    def test_move_in_pressure_past(self):
        t = _turnover(TODAY - timedelta(days=10), move_in_date=TODAY - timedelta(days=2))
        assert move_in_pressure(t, today=TODAY) == -2

    def test_move_in_pressure_none(self):
        t = _turnover(TODAY - timedelta(days=10))
        assert move_in_pressure(t, today=TODAY) is None

    def test_move_in_pressure_three_days_triggers_danger_priority(self):
        """Move-in in 3 days -> pressure 3 (used by priority for MOVE_IN_DANGER)."""
        t = _turnover(TODAY - timedelta(days=5), move_in_date=TODAY + timedelta(days=3))
        assert move_in_pressure(t, today=TODAY) == 3


class TestBreachSeverity:
    def test_breach_severity_breach_is_critical(self):
        t = _turnover(TODAY - timedelta(days=14))
        assert breach_severity(t, today=TODAY, threshold_days=14) == "CRITICAL"

    def test_breach_severity_warning_is_warning(self):
        t = _turnover(TODAY - timedelta(days=11))
        assert breach_severity(t, today=TODAY, threshold_days=14) == "WARNING"

    def test_breach_severity_ok_is_info(self):
        t = _turnover(TODAY - timedelta(days=5))
        assert breach_severity(t, today=TODAY, threshold_days=14) == "INFO"

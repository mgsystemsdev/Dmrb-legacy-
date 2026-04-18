"""Tests for domain.turnover_lifecycle — lifecycle phase computation."""

from __future__ import annotations

from datetime import date, timedelta

from domain.turnover_lifecycle import (
    PHASE_CANCELED,
    PHASE_CLOSED,
    PHASE_OCCUPIED,
    PHASE_ON_NOTICE,
    PHASE_PRE_NOTICE,
    PHASE_VACANT_NOT_READY,
    PHASE_VACANT_READY,
    days_since_move_out,
    days_to_be_ready,
    days_to_move_in,
    effective_move_out_date,
    is_open,
    lifecycle_phase,
    nvm_state,
    turnover_window_days,
    vacancy_days,
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


class TestLifecyclePhase:
    def test_canceled_returns_canceled(self):
        t = _turnover(TODAY, canceled_at="2025-06-10")
        assert lifecycle_phase(t, today=TODAY) == PHASE_CANCELED

    def test_closed_returns_closed(self):
        t = _turnover(TODAY, closed_at="2025-06-10")
        assert lifecycle_phase(t, today=TODAY) == PHASE_CLOSED

    def test_occupied_when_move_in_past(self):
        t = _turnover(TODAY - timedelta(days=30), move_in_date=TODAY - timedelta(days=1))
        assert lifecycle_phase(t, today=TODAY) == PHASE_OCCUPIED

    def test_vacant_ready_when_manual_ready(self):
        t = _turnover(TODAY - timedelta(days=5), manual_ready_status="Vacant Ready")
        assert lifecycle_phase(t, today=TODAY) == PHASE_VACANT_READY

    def test_on_notice_when_move_out_future(self):
        t = _turnover(TODAY + timedelta(days=10), manual_ready_status="On Notice")
        assert lifecycle_phase(t, today=TODAY) == PHASE_ON_NOTICE

    def test_pre_notice_when_move_out_future(self):
        t = _turnover(TODAY + timedelta(days=10))
        assert lifecycle_phase(t, today=TODAY) == PHASE_PRE_NOTICE

    def test_vacant_not_ready_when_move_out_past(self):
        t = _turnover(TODAY - timedelta(days=5))
        assert lifecycle_phase(t, today=TODAY) == PHASE_VACANT_NOT_READY


class TestDaysSinceMoveOut:
    def test_days_since_move_out(self):
        t = _turnover(TODAY - timedelta(days=7))
        assert days_since_move_out(t, today=TODAY) == 7

    def test_days_since_move_out_today(self):
        """Move-out today -> DV = 0."""
        t = _turnover(TODAY)
        assert days_since_move_out(t, today=TODAY) == 0

    def test_days_since_move_out_future(self):
        t = _turnover(TODAY + timedelta(days=3))
        assert days_since_move_out(t, today=TODAY) == -3


class TestDaysToMoveIn:
    def test_days_to_move_in(self):
        t = _turnover(TODAY - timedelta(days=10), move_in_date=TODAY + timedelta(days=5))
        assert days_to_move_in(t, today=TODAY) == 5

    def test_days_to_move_in_none(self):
        t = _turnover(TODAY)
        assert days_to_move_in(t, today=TODAY) is None


class TestDaysToBeReady:
    """DTBR = Days To Be Rented — purely a move-in countdown."""

    def test_no_move_in_returns_zero(self):
        t = _turnover(TODAY - timedelta(days=5))
        assert days_to_be_ready(t, [], today=TODAY) == 0

    def test_future_move_in(self):
        t = _turnover(TODAY - timedelta(days=5), move_in_date=TODAY + timedelta(days=8))
        assert days_to_be_ready(t, [], today=TODAY) == 8

    def test_move_in_today_returns_zero(self):
        t = _turnover(TODAY - timedelta(days=5), move_in_date=TODAY)
        assert days_to_be_ready(t, [], today=TODAY) == 0

    def test_move_in_past_clamped_to_zero(self):
        t = _turnover(TODAY - timedelta(days=10), move_in_date=TODAY - timedelta(days=3))
        assert days_to_be_ready(t, [], today=TODAY) == 0

    def test_tasks_ignored(self):
        """Tasks do not affect DTBR — only move-in matters."""
        t = _turnover(TODAY - timedelta(days=5), move_in_date=TODAY + timedelta(days=6))
        tasks = [
            {
                "task_id": 1,
                "required": True,
                "execution_status": "NOT_STARTED",
                "vendor_due_date": TODAY + timedelta(days=20),
            },
        ]
        assert days_to_be_ready(t, tasks, today=TODAY) == 6

    def test_pre1990_sentinel_ignored(self):
        """Legacy pre-1990 move_in_date is treated as absent."""
        t = _turnover(TODAY - timedelta(days=5), move_in_date=date(1900, 1, 1))
        assert days_to_be_ready(t, [], today=TODAY) == 0


class TestVacancyDays:
    def test_vacancy_days_with_move_in(self):
        t = _turnover(TODAY - timedelta(days=10), move_in_date=TODAY + timedelta(days=5))
        assert vacancy_days(t, today=TODAY) == 15

    def test_vacancy_days_no_move_in_past_move_out(self):
        t = _turnover(TODAY - timedelta(days=7))
        assert vacancy_days(t, today=TODAY) == 7

    def test_vacancy_days_no_move_in_future_move_out(self):
        t = _turnover(TODAY + timedelta(days=3))
        assert vacancy_days(t, today=TODAY) is None


class TestTurnoverWindowDays:
    def test_turnover_window_days(self):
        t = _turnover(TODAY - timedelta(days=10), move_in_date=TODAY + timedelta(days=5))
        assert turnover_window_days(t) == 15

    def test_turnover_window_days_none(self):
        t = _turnover(TODAY)
        assert turnover_window_days(t) is None


class TestEffectiveMoveOutDate:
    def test_effective_move_out_date_resolution_order(self):
        """Resolution: override -> confirmed -> scheduled -> move_out_date."""
        t = {
            **_turnover(TODAY - timedelta(days=10)),
            "scheduled_move_out_date": TODAY - timedelta(days=9),
            "confirmed_move_out_date": TODAY - timedelta(days=8),
        }
        assert effective_move_out_date(t) == TODAY - timedelta(days=8)

    def test_effective_move_out_date_fallback_to_move_out(self):
        t = _turnover(TODAY - timedelta(days=5))
        assert effective_move_out_date(t) == TODAY - timedelta(days=5)

    def test_effective_move_out_date_none_when_no_dates(self):
        t = {"turnover_id": 1, "move_out_date": None}
        assert effective_move_out_date(t) is None


class TestIsOpen:
    def test_is_open_true(self):
        t = _turnover(TODAY)
        assert is_open(t) is True

    def test_is_open_false_closed(self):
        t = _turnover(TODAY, closed_at="2025-06-10")
        assert is_open(t) is False

    def test_is_open_false_canceled(self):
        t = _turnover(TODAY, canceled_at="2025-06-10")
        assert is_open(t) is False


class TestNvmState:
    """5-state N/V/M label — mirrors operational Excel formula."""

    # ── terminal states ───────────────────────────────────────────────────────

    def test_canceled_returns_dash(self):
        t = _turnover(TODAY, canceled_at="2025-06-10")
        assert nvm_state(t, today=TODAY) == "—"

    def test_closed_returns_dash(self):
        t = _turnover(TODAY, closed_at="2025-06-10")
        assert nvm_state(t, today=TODAY) == "—"

    def test_no_move_out_returns_dash(self):
        t = {
            "turnover_id": 1,
            "move_out_date": None,
            "move_in_date": None,
            "closed_at": None,
            "canceled_at": None,
        }
        assert nvm_state(t, today=TODAY) == "—"

    # ── Move-In ───────────────────────────────────────────────────────────────

    def test_move_in_today(self):
        t = _turnover(TODAY - timedelta(days=10), move_in_date=TODAY)
        assert nvm_state(t, today=TODAY) == "Move-In"

    def test_move_in_past(self):
        t = _turnover(TODAY - timedelta(days=20), move_in_date=TODAY - timedelta(days=3))
        assert nvm_state(t, today=TODAY) == "Move-In"

    # ── SMI (vacant with scheduled future move-in) ────────────────────────────

    def test_smi_vacant_with_future_move_in(self):
        t = _turnover(TODAY - timedelta(days=5), move_in_date=TODAY + timedelta(days=7))
        assert nvm_state(t, today=TODAY) == "SMI"

    def test_smi_move_out_today_future_move_in(self):
        t = _turnover(TODAY, move_in_date=TODAY + timedelta(days=1))
        assert nvm_state(t, today=TODAY) == "SMI"

    # ── Vacant ────────────────────────────────────────────────────────────────

    def test_vacant_no_move_in(self):
        t = _turnover(TODAY - timedelta(days=5))
        assert nvm_state(t, today=TODAY) == "Vacant"

    def test_vacant_move_out_today_no_move_in(self):
        t = _turnover(TODAY)
        assert nvm_state(t, today=TODAY) == "Vacant"

    # ── Notice + SMI ──────────────────────────────────────────────────────────

    def test_notice_smi_future_move_out_and_future_move_in(self):
        t = _turnover(TODAY + timedelta(days=10), move_in_date=TODAY + timedelta(days=20))
        assert nvm_state(t, today=TODAY) == "Notice + SMI"

    # ── Notice ────────────────────────────────────────────────────────────────

    def test_notice_future_move_out_no_move_in(self):
        t = _turnover(TODAY + timedelta(days=10))
        assert nvm_state(t, today=TODAY) == "Notice"

    # ── Pre-1990 sentinel treated as absent ───────────────────────────────────

    def test_sentinel_move_in_pre1990_treated_as_absent(self):
        """A move_in_date before 1990 is a legacy sentinel and must be ignored."""
        t = _turnover(TODAY + timedelta(days=10), move_in_date=date(1900, 1, 1))
        assert nvm_state(t, today=TODAY) == "Notice"

    def test_sentinel_vacant_pre1990_move_in_shows_vacant(self):
        t = _turnover(TODAY - timedelta(days=5), move_in_date=date(1900, 1, 1))
        assert nvm_state(t, today=TODAY) == "Vacant"

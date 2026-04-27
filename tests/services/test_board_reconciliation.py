"""Tests for explicit board reconciliation entry point."""

from datetime import date
from unittest.mock import patch

from services.board_reconciliation import run_board_reconciliation_for_property


def test_run_board_reconciliation_invokes_five_steps_in_order():
    """Same sequence as board_service.get_board pre-read hooks."""
    calls: list[str] = []

    def track(name: str):
        def _inner(*args, **kwargs):
            calls.append(name)

        return _inner

    with (
        patch(
            "services.board_reconciliation.turnover_service.reconcile_open_turnovers_from_latest_available_units",
            side_effect=track("reconcile_au"),
        ),
        patch(
            "services.board_reconciliation.turnover_service.ensure_on_notice_turnovers_for_property",
            side_effect=track("on_notice"),
        ),
        patch(
            "services.board_reconciliation.lifecycle_automation_service.run_available_date_transition",
            side_effect=track("dv_transition"),
        ),
        patch(
            "services.board_reconciliation.turnover_service.backfill_placeholder_ready_dates",
            side_effect=track("backfill_ready"),
        ),
        patch(
            "services.board_reconciliation.turnover_service.backfill_tasks_for_property",
            side_effect=track("backfill_tasks"),
        ),
    ):
        run_board_reconciliation_for_property(
            1,
            today=date(2025, 6, 1),
            phase_ids=[10, 20],
        )

    assert calls == [
        "reconcile_au",
        "on_notice",
        "dv_transition",
        "backfill_ready",
        "backfill_tasks",
    ]

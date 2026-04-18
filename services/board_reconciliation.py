"""Board reconciliation — explicit pre-read mutations for a property.

Run after imports (or any time before treating DB state as board-true). The same
steps execute inside board_service.get_board before assembling rows; this module
exposes them for headless rebuilds and runbooks without implying Streamlit must
open the board.

Order and try/except behavior match board_service.get_board (legacy contract).
"""

from __future__ import annotations

import logging
from datetime import date

from services import turnover_service
from services.automation import lifecycle_automation_service

logger = logging.getLogger(__name__)


def run_board_reconciliation_for_property(
    property_id: int,
    *,
    today: date | None = None,
    phase_ids: list[int] | None = None,
) -> None:
    """Apply all board-time healing steps for *property_id* (writes to DB).

    Use the same *today* and *phase_ids* you will use for get_board / get_board_view
    so scope matches operator-visible board filters.

    Idempotent where underlying helpers are idempotent; safe to call after imports
    or before exports that load the board.
    """
    # Heal missed status updates from latest Available Units import for open turnovers.
    try:
        turnover_service.reconcile_open_turnovers_from_latest_available_units(
            property_id,
            today=today,
            phase_ids=phase_ids,
        )
    except Exception:
        logger.warning(
            "board_reconciliation_failed func=reconcile_open_turnovers_from_latest_available_units property_id=%s",
            property_id,
            exc_info=True,
        )
    # Ensure On Notice units with past available_date have turnovers
    try:
        turnover_service.ensure_on_notice_turnovers_for_property(
            property_id,
            today=today,
            phase_ids=phase_ids,
        )
    except Exception:
        logger.warning(
            "board_reconciliation_failed func=ensure_on_notice_turnovers_for_property property_id=%s",
            property_id,
            exc_info=True,
        )
    # Auto-transition On Notice → Vacant Not Ready when DV is 0..10
    try:
        lifecycle_automation_service.run_available_date_transition(
            property_id,
            today=today,
            phase_ids=phase_ids,
        )
    except Exception:
        logger.warning(
            "board_reconciliation_failed func=run_available_date_transition property_id=%s",
            property_id,
            exc_info=True,
        )
    # Backfill placeholder report_ready_date on turnovers where it is NULL
    try:
        turnover_service.backfill_placeholder_ready_dates(
            property_id,
            phase_ids=phase_ids,
        )
    except Exception:
        logger.warning(
            "board_reconciliation_failed func=backfill_placeholder_ready_dates property_id=%s",
            property_id,
            exc_info=True,
        )
    # Ensure every open turnover has tasks before building the board
    try:
        turnover_service.backfill_tasks_for_property(
            property_id,
            phase_ids=phase_ids,
        )
    except Exception:
        logger.warning(
            "board_reconciliation_failed func=backfill_tasks_for_property property_id=%s",
            property_id,
            exc_info=True,
        )

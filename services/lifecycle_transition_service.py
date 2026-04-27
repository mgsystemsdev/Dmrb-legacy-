"""Apply strict lifecycle phase transitions and append ``lifecycle_event`` rows."""

from __future__ import annotations

import logging
from datetime import date, datetime

from db.repository import lifecycle_event_repository, turnover_repository
from domain import turnover_lifecycle
from domain.availability_status import (
    MANUAL_READY_ON_NOTICE,
    MANUAL_READY_VACANT_NOT_READY,
    MANUAL_READY_VACANT_READY,
)
from services.turnover_service import TurnoverError, update_turnover
from services.write_guard import check_writes_enabled

logger = logging.getLogger(__name__)


def transition_turnover_phase(
    property_id: int,
    turnover_id: int,
    to_phase: str,
    actor: str,
    source: str,
    *,
    today: date | None = None,
    cancel_reason: str | None = None,
    move_in_date: date | None = None,
    payload: dict | None = None,
) -> dict:
    """Validate ``from_phase → to_phase``, mutate turnover, insert lifecycle_event.

    ``cancel_reason`` is required when ``to_phase`` is ``CANCELED``.

    ``move_in_date`` is used for ``VACANT_READY → OCCUPIED`` (defaults to ``today``).

    Raises :class:`TurnoverError` for business guard failures,
    :class:`turnover_lifecycle.TransitionError` for disallowed edges,
    or returns the turnover row after a successful transition (reloaded).
    """
    check_writes_enabled()
    today = today or date.today()

    existing = turnover_repository.get_by_id(turnover_id)
    if existing is None:
        raise TurnoverError(f"Turnover {turnover_id} not found.")
    if int(existing["property_id"]) != int(property_id):
        raise TurnoverError(f"Turnover {turnover_id} does not belong to property {property_id}.")

    from_phase = turnover_lifecycle.lifecycle_phase(existing, today)
    if from_phase == to_phase:
        return existing

    turnover_lifecycle.validate_transition(from_phase, to_phase)

    if to_phase == turnover_lifecycle.PHASE_CANCELED:
        if not (cancel_reason and str(cancel_reason).strip()):
            raise TurnoverError("cancel_reason is required for transition to CANCELED.")

    _apply_transition(
        existing,
        from_phase,
        to_phase,
        actor=actor,
        source=source,
        today=today,
        cancel_reason=cancel_reason,
        move_in_date=move_in_date,
    )

    final = turnover_repository.get_by_id(turnover_id)
    if final is None:
        raise TurnoverError(f"Turnover {turnover_id} missing after transition.")
    actual = turnover_lifecycle.lifecycle_phase(final, today)
    if actual != to_phase:
        raise TurnoverError(
            f"Lifecycle invariant failed: expected phase {to_phase!r}, got {actual!r} "
            f"after transition from {from_phase!r}."
        )

    try:
        lifecycle_event_repository.insert(
            property_id,
            turnover_id,
            to_phase,
            actor,
            source,
            from_phase=from_phase,
            payload=payload,
        )
    except Exception:
        logger.exception(
            "lifecycle_event insert failed after successful turnover mutation "
            "turnover_id=%s property_id=%s %s→%s",
            turnover_id,
            property_id,
            from_phase,
            to_phase,
        )
        raise

    return final


def _apply_transition(
    existing: dict,
    from_phase: str,
    to_phase: str,
    *,
    actor: str,
    source: str,
    today: date,
    cancel_reason: str | None,
    move_in_date: date | None,
) -> dict:
    tid = int(existing["turnover_id"])

    if to_phase == turnover_lifecycle.PHASE_CLOSED:
        return update_turnover(
            tid,
            actor=actor,
            source=source,
            closed_at=datetime.utcnow(),
        )

    if to_phase == turnover_lifecycle.PHASE_CANCELED:
        return update_turnover(
            tid,
            actor=actor,
            source=source,
            canceled_at=datetime.utcnow(),
            cancel_reason=str(cancel_reason).strip(),
        )

    if (
        from_phase == turnover_lifecycle.PHASE_PRE_NOTICE
        and to_phase == turnover_lifecycle.PHASE_ON_NOTICE
    ):
        return update_turnover(
            tid,
            actor=actor,
            source=source,
            manual_ready_status=MANUAL_READY_ON_NOTICE,
            availability_status="on notice",
        )

    if (
        from_phase == turnover_lifecycle.PHASE_ON_NOTICE
        and to_phase == turnover_lifecycle.PHASE_VACANT_NOT_READY
    ):
        fields: dict = {
            "manual_ready_status": MANUAL_READY_VACANT_NOT_READY,
            "availability_status": "vacant not ready",
        }
        move_out = existing.get("move_out_date")
        if move_out is not None and move_out > today:
            fields["move_out_date"] = today
        return update_turnover(tid, actor=actor, source=source, **fields)

    if (
        from_phase == turnover_lifecycle.PHASE_VACANT_NOT_READY
        and to_phase == turnover_lifecycle.PHASE_VACANT_READY
    ):
        return update_turnover(
            tid,
            actor=actor,
            source=source,
            manual_ready_status=MANUAL_READY_VACANT_READY,
            manual_ready_confirmed_at=datetime.utcnow(),
            availability_status="vacant ready",
        )

    if (
        from_phase == turnover_lifecycle.PHASE_VACANT_READY
        and to_phase == turnover_lifecycle.PHASE_VACANT_NOT_READY
    ):
        return update_turnover(
            tid,
            actor=actor,
            source=source,
            manual_ready_status=MANUAL_READY_VACANT_NOT_READY,
            manual_ready_confirmed_at=None,
            availability_status="vacant not ready",
        )

    if (
        from_phase == turnover_lifecycle.PHASE_VACANT_READY
        and to_phase == turnover_lifecycle.PHASE_OCCUPIED
    ):
        mid = move_in_date or today
        if mid > today:
            raise TurnoverError(
                "move_in_date must be on or before today for transition to OCCUPIED."
            )
        return update_turnover(
            tid,
            actor=actor,
            source=source,
            move_in_date=mid,
        )

    raise TurnoverError(f"No handler for transition {from_phase!r} → {to_phase!r} (unexpected).")

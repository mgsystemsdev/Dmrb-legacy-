"""Missing Move-Out resolution service.

Provides the operational queue for move-in rows that arrived without
an open turnover.  The manager supplies the missing move-out date;
the service creates the turnover and marks the exception resolved.
"""

from __future__ import annotations

import logging
from datetime import date

from db.repository import import_repository, audit_repository, turnover_repository
from domain.manual_override import should_apply_import_value
from services import scope_service, turnover_service
from services.write_guard import check_writes_enabled

logger = logging.getLogger(__name__)


def reconcile_pending_move_ins(property_id: int, user_id: int = 0) -> int:
    """Auto-resolve stale CONFLICT rows whose unit now has an open turnover with move_out_date.

    For each unresolved MOVE_IN_WITHOUT_OPEN_TURNOVER row:
    - If the unit has an open turnover with move_out_date set → apply move_in_date
      (respecting manual override rule) and mark the import row resolved.
    - Otherwise leave it in the queue (true orphan).

    Returns the number of rows resolved.
    """
    check_writes_enabled()
    phase_ids = scope_service.get_phase_scope(user_id, property_id)
    rows = import_repository.get_missing_move_out_rows(property_id, phase_ids=phase_ids)
    resolved = 0

    for row in rows:
        unit_id = row.get("unit_id")
        move_in_date = row.get("move_in_date")
        if not unit_id or not move_in_date:
            continue

        turnover = turnover_repository.get_open_by_unit(unit_id)
        if not turnover or not turnover.get("move_out_date"):
            continue  # true orphan — stays in queue

        # Respect manual override rule
        apply_val, clear_override = should_apply_import_value(
            turnover.get("move_in_date"),
            turnover.get("move_in_manual_override_at"),
            move_in_date,
        )
        if apply_val:
            updates: dict = {"move_in_date": move_in_date}
            if clear_override:
                updates["move_in_manual_override_at"] = None
            turnover_service.update_turnover(
                turnover["turnover_id"], actor="import", **updates
            )

        # Row is matched to a real turnover — resolve regardless of override
        import_repository.resolve_import_row(row["row_id"])
        resolved += 1

    return resolved


def list_missing_move_outs(property_id: int, user_id: int = 0) -> list[dict]:
    """Return unresolved missing-move-out exception rows for units in the active phase scope."""
    phase_ids = scope_service.get_phase_scope(user_id, property_id)
    return import_repository.get_missing_move_out_rows(property_id, phase_ids=phase_ids)


def resolve_missing_move_out(
    row_id: int,
    property_id: int,
    unit_id: int,
    move_out_date: date,
    *,
    move_in_date: date | None = None,
    actor: str = "manager",
) -> dict:
    """Create a turnover for a missing-move-out row and mark it resolved.

    Returns the newly created turnover dict.

    Raises ``turnover_service.TurnoverError`` if turnover creation fails.
    """
    check_writes_enabled()

    turnover = turnover_service.create_turnover(
        property_id=property_id,
        unit_id=unit_id,
        move_out_date=move_out_date,
        move_in_date=move_in_date,
        actor=actor,
    )

    audit_repository.insert(
        property_id=property_id,
        entity_type="turnover",
        entity_id=turnover["turnover_id"],
        field_name="import_source",
        old_value=None,
        new_value="turnover_created_from_missing_move_out_resolution",
        actor=actor,
        source="missing_move_out_service",
    )

    import_repository.resolve_import_row(row_id)

    return turnover

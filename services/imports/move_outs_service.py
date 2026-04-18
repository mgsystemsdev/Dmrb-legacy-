"""Move Outs report apply service.

Processes each row from the Move Outs CSV:
  1. Validate move-out date.
  2. Resolve / create unit.
  3. Create or update turnover (with manual-override protection).
  4. Post-process: track missing move-out absences and auto-cancel.
"""

from __future__ import annotations

import logging

from domain import import_outcomes
from domain.manual_override import should_apply_import_value
from domain.move_out_absence import should_cancel_turnover
from domain.unit_identity import normalize_unit_code
from db.repository import turnover_repository, audit_repository
from services import turnover_service
from services.imports import common

logger = logging.getLogger(__name__)


def apply(
    batch_id: int,
    rows: list[dict],
    property_id: int,
) -> dict:
    """Process Move Outs rows and record outcomes.

    Returns counters: ``{applied, conflict, invalid}``.
    """
    applied = 0
    conflict = 0
    invalid = 0
    seen_unit_ids: set[int] = set()

    for row in rows:
        unit_raw = str(row.get("Unit", ""))
        unit_norm = normalize_unit_code(unit_raw) if unit_raw else None
        move_out = common.parse_date(row.get("Move-Out Date"))

        # ── 1. Validate move-out date ────────────────────────────────────
        if move_out is None:
            common.write_import_row(
                property_id=property_id,
                batch_id=batch_id,
                row_data=row,
                status=import_outcomes.INVALID,
                reason=import_outcomes.MISSING_MOVE_OUT_DATE,
                unit_code_raw=unit_raw,
                unit_code_norm=unit_norm,
            )
            invalid += 1
            continue

        # ── 2. Ensure unit exists ────────────────────────────────────────
        unit = _resolve_or_create_unit(property_id, unit_raw, unit_norm)
        unit_id = unit["unit_id"]

        # ── 3. Look up open turnover ─────────────────────────────────────
        turnover = turnover_repository.get_open_by_unit(unit_id)

        if turnover is None:
            # ── 4. No open turnover → create one ─────────────────────────
            status, reason = _handle_create_turnover(
                property_id, unit_id, move_out, batch_id,
            )
        else:
            # ── 5. Open turnover → apply override rule & update ──────────
            status, reason = _handle_update_turnover(
                turnover, move_out, property_id, batch_id,
            )

        common.write_import_row(
            property_id=property_id,
            batch_id=batch_id,
            row_data=row,
            status=status,
            reason=reason,
            unit_code_raw=unit_raw,
            unit_code_norm=unit_norm,
            move_out_date=move_out,
        )

        if status == import_outcomes.OK:
            applied += 1
            seen_unit_ids.add(unit_id)
        elif status == import_outcomes.SKIPPED_OVERRIDE:
            conflict += 1
            seen_unit_ids.add(unit_id)
        elif status == import_outcomes.CONFLICT:
            conflict += 1
        elif status == import_outcomes.INVALID:
            invalid += 1

    # ── 6. Post-processing: missing move-out count & auto-cancel ─────────
    _post_process_missing_moveouts(property_id, seen_unit_ids)

    return {"applied": applied, "conflict": conflict, "invalid": invalid}


# ── Internal helpers ─────────────────────────────────────────────────────────

def _resolve_or_create_unit(
    property_id: int,
    unit_raw: str,
    unit_norm: str,
) -> dict:
    return common.resolve_or_create_unit(property_id, unit_raw, unit_norm)


def _handle_create_turnover(
    property_id: int,
    unit_id: int,
    move_out_date,
    batch_id: int,
) -> tuple[str, str | None]:
    """Create a new turnover and return ``(status, reason)``."""
    try:
        turnover = turnover_service.create_turnover(
            property_id=property_id,
            unit_id=unit_id,
            move_out_date=move_out_date,
            scheduled_move_out_date=move_out_date,
            actor="import",
        )
        audit_repository.insert(
            property_id=property_id,
            entity_type="turnover",
            entity_id=turnover["turnover_id"],
            field_name="import_source",
            old_value=None,
            new_value="turnover_created_from_move_out_import",
            actor="import",
            source="move_outs_service",
        )
        return (import_outcomes.OK, None)
    except turnover_service.TurnoverError as exc:
        logger.warning("Turnover creation failed for unit %s: %s", unit_id, exc)
        return (import_outcomes.CONFLICT, "TURNOVER_CREATION_FAILED")


def _handle_update_turnover(
    turnover: dict,
    incoming_move_out,
    property_id: int,
    batch_id: int,
) -> tuple[str, str | None]:
    """Apply override rule and update an existing turnover.

    Returns ``(status, reason)``.
    """
    turnover_id = turnover["turnover_id"]
    current_scheduled = turnover.get("scheduled_move_out_date")
    override_at = turnover.get("move_out_manual_override_at")

    apply_val, clear_override = should_apply_import_value(
        current_scheduled, override_at, incoming_move_out,
    )

    if not apply_val:
        audit_repository.insert(
            property_id=property_id,
            entity_type="turnover",
            entity_id=turnover_id,
            field_name="scheduled_move_out_date",
            old_value=str(current_scheduled) if current_scheduled else None,
            new_value=str(incoming_move_out),
            actor="import",
            source="move_outs_service:override_skip",
        )
        return (
            import_outcomes.SKIPPED_OVERRIDE,
            import_outcomes.IMPORT_SKIPPED_DUE_TO_MANUAL_OVERRIDE,
        )

    # Build the update payload
    updates: dict = {}

    if current_scheduled != incoming_move_out:
        updates["scheduled_move_out_date"] = incoming_move_out

    # If no legal confirmation exists and move_out_date differs, update it too
    if not turnover.get("legal_confirmation_source"):
        if turnover.get("move_out_date") != incoming_move_out:
            updates["move_out_date"] = incoming_move_out

    if clear_override:
        updates["move_out_manual_override_at"] = None

    if updates:
        turnover_service.update_turnover(
            turnover_id, actor="import", **updates,
        )

    return (import_outcomes.OK, None)


def _post_process_missing_moveouts(
    property_id: int,
    seen_unit_ids: set[int],
) -> None:
    """Increment / reset missing-moveout counts and auto-cancel.

    Only turnovers that have Move-Out report evidence
    (``scheduled_move_out_date`` is set) participate in missing-moveout
    tracking.  Turnovers created solely from Available Units fallback
    will not have this field and must not be auto-canceled for absence
    from Move-Out reports.
    """
    open_turnovers = turnover_repository.get_open_by_property(property_id)

    for turnover in open_turnovers:
        turnover_id = turnover["turnover_id"]
        unit_id = turnover["unit_id"]
        current_count = turnover.get("missing_moveout_count", 0)

        if unit_id in seen_unit_ids:
            # Unit appeared — reset counter
            if current_count != 0:
                turnover_service.update_turnover(
                    turnover_id,
                    actor="import",
                    missing_moveout_count=0,
                )
        else:
            # Skip turnovers that have never been seen in a Move-Out report
            if turnover.get("scheduled_move_out_date") is None:
                continue

            # Unit absent — increment counter
            new_count = current_count + 1
            if should_cancel_turnover(new_count):
                turnover_service.cancel_turnover(
                    turnover_id,
                    reason="Move-out disappeared from report twice",
                    actor="import",
                )
            else:
                turnover_service.update_turnover(
                    turnover_id,
                    actor="import",
                    missing_moveout_count=new_count,
                )

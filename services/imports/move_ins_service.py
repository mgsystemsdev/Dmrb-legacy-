"""Move Ins (Pending Move-Ins) report apply service.

Processes each row from the Move Ins CSV:
  1. Validate move-in date.
  2. Resolve / create unit.
  3. Look up open turnover — CONFLICT if missing.
  4. Apply manual-override rule on move_in_date and update turnover.

Does NOT close turnovers.  Does NOT create turnovers.
"""

from __future__ import annotations

import logging

from db.repository import audit_repository, turnover_repository
from domain import import_outcomes
from domain.manual_override import should_apply_import_value
from domain.unit_identity import normalize_unit_code
from services import turnover_service
from services.imports import common

logger = logging.getLogger(__name__)


def apply(
    batch_id: int,
    rows: list[dict],
    property_id: int,
) -> dict:
    """Process Move Ins rows and record outcomes.

    Returns counters: ``{applied, conflict, invalid}``.
    """
    applied = 0
    conflict = 0
    invalid = 0

    for row in rows:
        unit_raw = str(row.get("Unit", ""))
        unit_norm = normalize_unit_code(unit_raw) if unit_raw else None
        move_in = common.parse_date(row.get("Move In Date"))

        # ── 1. Validate move-in date ─────────────────────────────────────
        if move_in is None:
            common.write_import_row(
                property_id=property_id,
                batch_id=batch_id,
                row_data=row,
                status=import_outcomes.INVALID,
                reason=import_outcomes.MISSING_MOVE_IN_DATE,
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
            # No open turnover — record CONFLICT, do NOT create turnover
            common.write_import_row(
                property_id=property_id,
                batch_id=batch_id,
                row_data=row,
                status=import_outcomes.CONFLICT,
                reason=import_outcomes.MOVE_IN_WITHOUT_OPEN_TURNOVER,
                unit_code_raw=unit_raw,
                unit_code_norm=unit_norm,
                move_in_date=move_in,
            )
            conflict += 1
            continue

        # ── 4. Open turnover exists — apply override rule & update ───────
        status, reason = _handle_update_move_in(
            turnover,
            move_in,
            property_id,
        )

        common.write_import_row(
            property_id=property_id,
            batch_id=batch_id,
            row_data=row,
            status=status,
            reason=reason,
            unit_code_raw=unit_raw,
            unit_code_norm=unit_norm,
            move_in_date=move_in,
        )

        if status == import_outcomes.OK:
            applied += 1
        elif status == import_outcomes.SKIPPED_OVERRIDE:
            conflict += 1
        elif status == import_outcomes.CONFLICT:
            conflict += 1

    return {"applied": applied, "conflict": conflict, "invalid": invalid}


# ── Internal helpers ─────────────────────────────────────────────────────────


def _resolve_or_create_unit(
    property_id: int,
    unit_raw: str,
    unit_norm: str,
) -> dict:
    return common.resolve_or_create_unit(property_id, unit_raw, unit_norm)


def _handle_update_move_in(
    turnover: dict,
    incoming_move_in,
    property_id: int,
) -> tuple[str, str | None]:
    """Apply override rule for move_in_date and update turnover.

    Returns ``(status, reason)``.
    """
    turnover_id = turnover["turnover_id"]
    current_move_in = turnover.get("move_in_date")
    override_at = turnover.get("move_in_manual_override_at")

    apply_val, clear_override = should_apply_import_value(
        current_move_in,
        override_at,
        incoming_move_in,
    )

    if not apply_val:
        audit_repository.insert(
            property_id=property_id,
            entity_type="turnover",
            entity_id=turnover_id,
            field_name="move_in_date",
            old_value=str(current_move_in) if current_move_in else None,
            new_value=str(incoming_move_in),
            actor="import",
            source="move_ins_service:override_skip",
        )
        return (
            import_outcomes.SKIPPED_OVERRIDE,
            import_outcomes.IMPORT_SKIPPED_DUE_TO_MANUAL_OVERRIDE,
        )

    updates: dict = {}

    if current_move_in != incoming_move_in:
        updates["move_in_date"] = incoming_move_in

    if clear_override:
        updates["move_in_manual_override_at"] = None

    if updates:
        turnover_service.update_turnover(
            turnover_id,
            actor="import",
            **updates,
        )

    return (import_outcomes.OK, None)

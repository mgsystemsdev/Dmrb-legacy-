"""Available Units report apply service.

Processes each row from the Available Units CSV:
  1. Normalize status and parse dates.
  2. Resolve / create unit (when status allows turnover creation).
  3. Create turnover for vacant units without one, or update readiness
     and availability fields on existing turnovers.
  4. Manual-override protection on report_ready_date and availability_status.
  5. Vacancy invariant: after all rows, clear stale availability_status on
     open turnovers whose units are absent from this file.
"""

from __future__ import annotations

import logging

from domain import import_outcomes
from domain.availability_status import (
    availability_status_to_manual_ready_status,
    status_allows_turnover_creation,
    status_is_on_notice,
    status_is_vacant,
)
from domain.manual_override import should_apply_import_value
from domain.unit_identity import normalize_unit_code
from db.repository import (
    turnover_repository,
    audit_repository,
    unit_repository,
    unit_on_notice_snapshot_repository,
)
from services import turnover_service
from services.imports import common

logger = logging.getLogger(__name__)


def apply(
    batch_id: int,
    rows: list[dict],
    property_id: int,
) -> dict:
    """Process Available Units rows and record outcomes.

    Returns counters: ``{applied, conflict, invalid}``.
    """
    applied = 0
    conflict = 0
    invalid = 0
    seen_unit_ids: set[int] = set()

    for row in rows:
        unit_raw = str(row.get("Unit", ""))
        unit_norm = normalize_unit_code(unit_raw) if unit_raw else None
        raw_status = str(row.get("Status", "")).strip()
        available_date = common.parse_date(row.get("Available Date"))
        move_in_ready_date = common.parse_date(row.get("Move-In Ready Date"))
        allows_creation = status_allows_turnover_creation(raw_status) if raw_status else False
        on_notice = status_is_on_notice(raw_status) if raw_status else False

        # ── 1. Ensure unit exists (when status allows creation or is on notice) ─────
        if not unit_norm:
            common.write_import_row(
                property_id=property_id,
                batch_id=batch_id,
                row_data=row,
                status=import_outcomes.IGNORED,
                reason=import_outcomes.NO_OPEN_TURNOVER_FOR_READY_DATE,
                unit_code_raw=unit_raw,
                unit_code_norm=unit_norm,
            )
            invalid += 1
            continue

        if allows_creation or on_notice:
            unit = _resolve_or_create_unit(property_id, unit_raw, unit_norm)
        else:
            unit = unit_repository.get_by_code_norm(property_id, unit_norm)
            if unit is None:
                common.write_import_row(
                    property_id=property_id,
                    batch_id=batch_id,
                    row_data=row,
                    status=import_outcomes.IGNORED,
                    reason=import_outcomes.NO_OPEN_TURNOVER_FOR_READY_DATE,
                    unit_code_raw=unit_raw,
                    unit_code_norm=unit_norm,
                )
                conflict += 1
                continue

        unit_id = unit["unit_id"]
        seen_unit_ids.add(unit_id)

        # ── 2. Look up open turnover ─────────────────────────────────────
        turnover = turnover_repository.get_open_by_unit(unit_id)

        if turnover is None:
            status, reason = _handle_no_turnover(
                property_id, unit_id, raw_status, available_date,
                move_in_ready_date, allows_creation, batch_id,
            )
        else:
            status, reason = _handle_update_turnover(
                turnover, raw_status, available_date,
                move_in_ready_date, property_id,
            )

        common.write_import_row(
            property_id=property_id,
            batch_id=batch_id,
            row_data=row,
            status=status,
            reason=reason,
            unit_code_raw=unit_raw,
            unit_code_norm=unit_norm,
        )

        if status == import_outcomes.OK:
            applied += 1
        elif status == import_outcomes.SKIPPED_OVERRIDE:
            conflict += 1
        elif status == import_outcomes.CONFLICT:
            conflict += 1
        elif status == import_outcomes.IGNORED:
            conflict += 1
        elif status == import_outcomes.INVALID:
            invalid += 1

    # ── 3. Post-processing: vacancy invariant ──────────────────────────
    _post_process_missing_available_units(property_id, seen_unit_ids)

    return {"applied": applied, "conflict": conflict, "invalid": invalid}


# ── Internal helpers ─────────────────────────────────────────────────────────

def _resolve_or_create_unit(
    property_id: int,
    unit_raw: str,
    unit_norm: str,
) -> dict:
    return common.resolve_or_create_unit(property_id, unit_raw, unit_norm)


def _handle_no_turnover(
    property_id: int,
    unit_id: int,
    raw_status: str,
    available_date,
    move_in_ready_date,
    allows_creation: bool,
    batch_id: int,
) -> tuple[str, str | None]:
    """Handle a row when no open turnover exists for the unit.

    - Vacant/beacon: create turnover and set status (OK).
    - On Notice: do not create turnover; upsert unit_on_notice_snapshot for midnight
      automation, then return IGNORED (ON_NOTICE_PENDING_AVAILABLE_DATE).
    """
    on_notice = status_is_on_notice(raw_status) if raw_status else False
    if not allows_creation and not on_notice:
        return (
            import_outcomes.IGNORED,
            import_outcomes.NO_OPEN_TURNOVER_FOR_READY_DATE,
        )

    if available_date is None:
        return (
            import_outcomes.INVALID,
            import_outcomes.MISSING_AVAILABLE_DATE,
        )

    # On Notice: IGNORED; effective status and turnover creation handled on board load.
    if on_notice and not allows_creation:
        unit_on_notice_snapshot_repository.upsert(
            property_id=property_id,
            unit_id=unit_id,
            available_date=available_date,
            move_in_ready_date=move_in_ready_date,
        )
        return (
            import_outcomes.IGNORED,
            import_outcomes.ON_NOTICE_PENDING_AVAILABLE_DATE,
        )

    # Vacant/beacon: create turnover with move_out_date = available_date
    try:
        turnover = turnover_service.create_turnover(
            property_id=property_id,
            unit_id=unit_id,
            move_out_date=available_date,
            actor="import",
        )
        audit_repository.insert(
            property_id=property_id,
            entity_type="turnover",
            entity_id=turnover["turnover_id"],
            field_name="import_source",
            old_value=None,
            new_value="turnover_created_from_available_units_import",
            actor="import",
            source="available_units_service",
        )
        norm_status = raw_status.strip().lower() if raw_status else None
        initial_fields: dict = {
            "available_date": available_date,
            "availability_status": norm_status,
        }
        manual_ready = availability_status_to_manual_ready_status(norm_status)
        if manual_ready is not None:
            initial_fields["manual_ready_status"] = manual_ready
        if move_in_ready_date is not None:
            initial_fields["report_ready_date"] = move_in_ready_date
        turnover_service.update_turnover(
            turnover["turnover_id"],
            actor="import",
            **initial_fields,
        )
        return (
            import_outcomes.OK,
            import_outcomes.CREATED_TURNOVER_FROM_AVAILABILITY,
        )
    except turnover_service.TurnoverError as exc:
        logger.warning("Turnover creation failed for unit %s: %s", unit_id, exc)
        return (import_outcomes.CONFLICT, "TURNOVER_CREATION_FAILED")


def _handle_update_turnover(
    turnover: dict,
    raw_status: str,
    available_date,
    move_in_ready_date,
    property_id: int,
) -> tuple[str, str | None]:
    """Apply override rules and update readiness / availability fields.

    Returns ``(status, reason)``.
    """
    turnover_id = turnover["turnover_id"]
    updates: dict = {}
    skipped_fields: list[str] = []

    # ── Override check for report_ready_date ──────────────────────────────
    if move_in_ready_date is not None:
        current_ready = turnover.get("report_ready_date")
        ready_override_at = turnover.get("ready_manual_override_at")

        apply_ready, clear_ready = should_apply_import_value(
            current_ready, ready_override_at, move_in_ready_date,
        )

        if apply_ready:
            if current_ready != move_in_ready_date:
                updates["report_ready_date"] = move_in_ready_date
            if clear_ready:
                updates["ready_manual_override_at"] = None
        else:
            skipped_fields.append("report_ready_date")

    # ── Override check for availability_status ────────────────────────────
    # Bug 4 fix: only evaluate override/update when incoming value is present
    norm_status = raw_status.strip().lower() if raw_status else None
    if norm_status:
        current_status = turnover.get("availability_status")
        status_override_at = turnover.get("status_manual_override_at")

        apply_status, clear_status = should_apply_import_value(
            current_status, status_override_at, norm_status,
        )

        if apply_status:
            if current_status != norm_status:
                updates["availability_status"] = norm_status
                # Sync canonical manual_ready_status for lifecycle/automation
                manual_ready = availability_status_to_manual_ready_status(norm_status)
                if manual_ready is not None:
                    updates["manual_ready_status"] = manual_ready
            if clear_status:
                updates["status_manual_override_at"] = None
        else:
            skipped_fields.append("availability_status")

    # ── available_date always updates (no separate override) ─────────────
    if available_date is not None:
        current_avail = turnover.get("available_date")
        if current_avail != available_date:
            updates["available_date"] = available_date

    # ── Apply updates ────────────────────────────────────────────────────
    if updates:
        turnover_service.update_turnover(
            turnover_id, actor="import", **updates,
        )

    # ── Bug 1 fix: always audit each skipped field, even when other
    #    fields updated successfully (partial override skip). ──────────────
    if skipped_fields:
        for field in skipped_fields:
            audit_repository.insert(
                property_id=property_id,
                entity_type="turnover",
                entity_id=turnover_id,
                field_name=field,
                old_value=None,
                new_value="import_skipped_due_to_manual_override",
                actor="import",
                source="available_units_service:override_skip",
            )
        if not updates:
            return (
                import_outcomes.SKIPPED_OVERRIDE,
                import_outcomes.IMPORT_SKIPPED_DUE_TO_MANUAL_OVERRIDE,
            )
        return (
            import_outcomes.OK,
            import_outcomes.PARTIAL_OVERRIDE_SKIP,
        )

    return (import_outcomes.OK, None)


def _post_process_missing_available_units(
    property_id: int,
    seen_unit_ids: set[int],
) -> None:
    """Clear stale vacancy status on turnovers whose units left the report.

    When a unit was previously marked as vacant (via an earlier Available
    Units import) but is absent from the current file, clear its
    ``availability_status`` — the unit is likely leased or no longer
    available.  Manual overrides are respected.
    """
    open_turnovers = turnover_repository.get_open_by_property(property_id)

    for turnover in open_turnovers:
        if turnover["unit_id"] in seen_unit_ids:
            continue

        current_status = turnover.get("availability_status")
        if not status_is_vacant(current_status):
            continue

        apply_status, clear_override = should_apply_import_value(
            current_status,
            turnover.get("status_manual_override_at"),
            None,
        )

        if not apply_status:
            audit_repository.insert(
                property_id=property_id,
                entity_type="turnover",
                entity_id=turnover["turnover_id"],
                field_name="availability_status",
                old_value=current_status,
                new_value=None,
                actor="import",
                source="available_units_service:missing_unit_override_skip",
            )
            continue

        updates: dict = {"availability_status": None}
        if clear_override:
            updates["status_manual_override_at"] = None

        turnover_service.update_turnover(
            turnover["turnover_id"],
            actor="import",
            **updates,
        )

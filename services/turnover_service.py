"""Turnover service — coordinates turnover lifecycle operations.

Enforces invariants:
  - One open turnover per unit.
  - Turnover requires a move-out date.
  - Close/cancel are terminal and mutually exclusive.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from db.connection import transaction
from db.repository import (
    audit_repository,
    import_repository,
    turnover_repository,
    unit_repository,
)
from domain import turnover_lifecycle
from domain.availability_status import (
    availability_status_to_manual_ready_status,
    status_is_on_notice,
)
from domain.manual_override import should_apply_import_value
from domain.unit_identity import normalize_unit_code
from services import risk_service, task_service
from services.write_guard import check_writes_enabled

logger = logging.getLogger(__name__)

PLACEHOLDER_READY_DATE_OFFSET_DAYS = 10


class TurnoverError(Exception):
    pass


def backfill_tasks_for_property(property_id: int, *, phase_ids=None):
    """
    Temporary no-op to unblock board reconciliation.
    """
    return


def create_turnover(
    property_id: int,
    unit_id: int,
    move_out_date: date,
    *,
    move_in_date: date | None = None,
    scheduled_move_out_date: date | None = None,
    actor: str = "system",
) -> dict:
    check_writes_enabled()
    unit = unit_repository.get_by_id(unit_id)
    if unit is None:
        raise TurnoverError(f"Unit {unit_id} does not exist.")
    if not unit.get("is_active"):
        raise TurnoverError(f"Unit {unit_id} is inactive.")

    existing = turnover_repository.get_open_by_unit(unit_id)
    if existing is not None:
        raise TurnoverError(
            f"Unit {unit_id} already has an open turnover (ID {existing['turnover_id']})."
        )

    phase_id = unit.get("phase_id")
    if phase_id is None:
        raise TurnoverError(f"Unit {unit_id} has no phase assigned; cannot create turnover tasks.")

    with transaction():
        turnover = turnover_repository.insert(
            property_id,
            unit_id,
            move_out_date,
            move_in_date=move_in_date,
            scheduled_move_out_date=scheduled_move_out_date,
        )
        turnover_id = turnover["turnover_id"]

        audit_repository.insert(
            property_id=property_id,
            entity_type="turnover",
            entity_id=turnover_id,
            field_name="created",
            old_value=None,
            new_value=str(turnover_id),
            actor=actor,
            source="turnover_service",
        )

        placeholder_ready = move_out_date + timedelta(days=PLACEHOLDER_READY_DATE_OFFSET_DAYS)
        turnover = turnover_repository.update(
            turnover_id,
            report_ready_date=placeholder_ready,
        )
        audit_repository.insert(
            property_id=property_id,
            entity_type="turnover",
            entity_id=turnover_id,
            field_name="report_ready_date",
            old_value=None,
            new_value=str(placeholder_ready),
            actor=actor,
            source="turnover_service.placeholder",
        )

        # Record unit moving for Work Order Validator
        try:
            from services.unit_movings_service import record_unit_moving

            record_unit_moving(unit["unit_code_norm"], move_out_date)
        except Exception:
            # We log but don't fail the whole transaction for unit_movings (non-critical)
            logger.exception("Failed to record unit moving during turnover creation")

        # Auto-create pipeline tasks (strictly required)
        task_service.ensure_default_templates_for_phase(property_id, phase_id)
        if not task_service.has_templates_for_phase(phase_id):
            raise TurnoverError(
                f"Phase {phase_id} has no active task templates; cannot create turnover."
            )

        tasks = task_service.instantiate_templates(
            property_id,
            turnover_id,
            phase_id,
            move_out_date,
            actor=actor,
        )
        if not tasks:
            raise TurnoverError(
                f"No tasks were generated for turnover {turnover_id} (phase {phase_id}); "
                "turnover creation aborted."
            )

        audit_repository.insert(
            property_id=property_id,
            entity_type="turnover",
            entity_id=turnover_id,
            field_name="pipeline_tasks",
            old_value=None,
            new_value=f"Generated {len(tasks)} tasks.",
            actor=actor,
            source="turnover_service",
        )

        evaluation_result = risk_service.evaluate_sla_state(turnover)
        risk_service.sync_risk_from_sla(turnover, evaluation_result)

        return turnover


def update_turnover(
    turnover_id: int,
    *,
    actor: str = "system",
    source: str = "turnover_service",
    **fields,
) -> dict:
    check_writes_enabled()
    existing = turnover_repository.get_by_id(turnover_id)
    if existing is None:
        raise TurnoverError(f"Turnover {turnover_id} not found.")
    if not turnover_lifecycle.is_open(existing):
        raise TurnoverError(f"Turnover {turnover_id} is closed or canceled.")

    updated = turnover_repository.update(turnover_id, **fields)

    for key, new_val in fields.items():
        old_val = existing.get(key)
        if str(old_val) != str(new_val):
            audit_repository.insert(
                property_id=existing["property_id"],
                entity_type="turnover",
                entity_id=turnover_id,
                field_name=key,
                old_value=str(old_val) if old_val is not None else None,
                new_value=str(new_val) if new_val is not None else None,
                actor=actor,
                source=source,
            )

    evaluation_result = risk_service.evaluate_sla_state(updated)
    risk_service.sync_risk_from_sla(updated, evaluation_result)

    return updated


def close_turnover(turnover_id: int, actor: str = "system") -> dict:
    check_writes_enabled()
    existing = turnover_repository.get_by_id(turnover_id)
    if existing is None:
        raise TurnoverError(f"Turnover {turnover_id} not found.")
    if not turnover_lifecycle.is_open(existing):
        raise TurnoverError(f"Turnover {turnover_id} is already closed or canceled.")

    return update_turnover(
        turnover_id,
        actor=actor,
        closed_at=datetime.utcnow(),
    )


def cancel_turnover(
    turnover_id: int,
    reason: str,
    actor: str = "system",
) -> dict:
    check_writes_enabled()
    existing = turnover_repository.get_by_id(turnover_id)
    if existing is None:
        raise TurnoverError(f"Turnover {turnover_id} not found.")
    if not turnover_lifecycle.is_open(existing):
        raise TurnoverError(f"Turnover {turnover_id} is already closed or canceled.")

    return update_turnover(
        turnover_id,
        actor=actor,
        canceled_at=datetime.utcnow(),
        cancel_reason=reason,
    )


def ensure_on_notice_turnovers_for_property(
    property_id: int,
    today: date | None = None,
    phase_ids: list[int] | None = None,
) -> dict:
    """Create turnovers for units that are On Notice with available_date <= today and no open turnover.

    Reads the latest completed Available Units import batch; for each On Notice row
    with available_date in the past or today, ensures an open turnover exists
    (creates via create_turnover so tasks, risk, audit run). Idempotent.
    Does not modify existing turnovers (Vacant Ready, Vacant Not Ready, or any other);
    only creates when get_open_by_unit(unit_id) is None. Called from board load.
    """
    check_writes_enabled()
    if today is None:
        today = date.today()

    from services.imports.common import parse_date

    batches = import_repository.get_batches_by_property(property_id, limit=200)
    batch = None
    for b in batches:
        if b.get("report_type") == "AVAILABLE_UNITS" and b.get("status") == "COMPLETED":
            batch = b
            break
    if batch is None:
        return {"created": 0, "errors": []}

    rows = import_repository.get_rows_by_batch(batch["batch_id"])
    created = 0
    errors: list[str] = []

    for row in rows:
        raw = row.get("raw_json") or {}
        unit_raw = raw.get("Unit") or row.get("unit_code_norm") or ""
        unit_norm = normalize_unit_code(str(unit_raw)) if unit_raw else None
        if not unit_norm:
            continue

        raw_status = (raw.get("Status") or "").strip()
        if not status_is_on_notice(raw_status):
            continue

        available_date = parse_date(raw.get("Available Date"))
        move_in_ready_date = parse_date(raw.get("Move-In Ready Date"))

        if available_date is None or available_date > today:
            continue

        unit = unit_repository.get_by_code_norm(property_id, unit_norm)
        if unit is None:
            continue
        if phase_ids is not None and unit.get("phase_id") not in phase_ids:
            continue

        unit_id = unit["unit_id"]
        if turnover_repository.get_open_by_unit(unit_id) is not None:
            continue

        try:
            turnover = create_turnover(
                property_id=property_id,
                unit_id=unit_id,
                move_out_date=available_date,
                actor="system",
            )
            turnover_id = turnover["turnover_id"]
            initial_fields: dict = {
                "availability_status": "vacant not ready",
                "manual_ready_status": "Vacant Not Ready",
                "available_date": available_date,
            }
            if move_in_ready_date is not None:
                initial_fields["report_ready_date"] = move_in_ready_date
            update_turnover(turnover_id, actor="system", **initial_fields)
            audit_repository.insert(
                property_id=property_id,
                entity_type="turnover",
                entity_id=turnover_id,
                field_name="lifecycle_transition",
                old_value=None,
                new_value="turnover_created_by_ensure_on_notice_turnovers",
                actor="system",
                source="turnover_service",
            )
            created += 1
        except TurnoverError as exc:
            err = f"unit_id={unit_id}: {exc}"
            errors.append(err)
            logger.warning("ensure_on_notice_turnovers: %s", err)
        except Exception as exc:
            err = f"unit_id={unit_id}: {exc}"
            errors.append(err)
            logger.exception("ensure_on_notice_turnovers failed for unit %s", unit_id)

    return {"created": created, "errors": errors}


def reconcile_open_turnovers_from_latest_available_units(
    property_id: int,
    *,
    today: date | None = None,
    phase_ids: list[int] | None = None,
) -> dict:
    """Reapply latest Available Units status fields to existing open turnovers.

    This is a healing reconciliation for cases where historical import rows were
    stored with inconsistent normalized unit codes and missed existing turnovers.
    It matches rows by normalized raw_json["Unit"] (source of truth), then applies
    status/date fields to the open turnover when override rules allow updates.
    """
    check_writes_enabled()
    if today is None:
        today = date.today()

    from services.imports.common import parse_date

    batches = import_repository.get_batches_by_property(property_id, limit=200)
    latest_batch = None
    for b in batches:
        if b.get("report_type") == "AVAILABLE_UNITS" and b.get("status") == "COMPLETED":
            latest_batch = b
            break
    if latest_batch is None:
        return {"updated": 0, "rows_seen": 0}

    rows = import_repository.get_rows_by_batch(latest_batch["batch_id"])
    updated = 0
    rows_seen = 0

    for row in rows:
        raw = row.get("raw_json") or {}
        unit_raw = raw.get("Unit") or row.get("unit_code_norm") or ""
        unit_norm = normalize_unit_code(str(unit_raw)) if unit_raw else None
        if not unit_norm:
            continue

        unit = unit_repository.get_by_code_norm(property_id, unit_norm)
        if unit is None:
            continue
        if phase_ids is not None and unit.get("phase_id") not in phase_ids:
            continue

        turnover = turnover_repository.get_open_by_unit(unit["unit_id"])
        if turnover is None:
            continue

        rows_seen += 1
        updates: dict = {}

        raw_status = (raw.get("Status") or "").strip().lower() or None
        if raw_status is not None:
            current_status = turnover.get("availability_status")
            apply_status, clear_status = should_apply_import_value(
                current_status,
                turnover.get("status_manual_override_at"),
                raw_status,
            )
            if apply_status:
                if current_status != raw_status:
                    updates["availability_status"] = raw_status
                    manual_ready = availability_status_to_manual_ready_status(raw_status)
                    if manual_ready is not None:
                        updates["manual_ready_status"] = manual_ready
                if clear_status:
                    updates["status_manual_override_at"] = None

        available_date = parse_date(raw.get("Available Date"))
        if available_date is not None and turnover.get("available_date") != available_date:
            updates["available_date"] = available_date

        move_in_ready_date = parse_date(raw.get("Move-In Ready Date"))
        if move_in_ready_date is not None:
            current_ready = turnover.get("report_ready_date")
            apply_ready, clear_ready = should_apply_import_value(
                current_ready,
                turnover.get("ready_manual_override_at"),
                move_in_ready_date,
            )
            if apply_ready:
                if current_ready != move_in_ready_date:
                    updates["report_ready_date"] = move_in_ready_date
                if clear_ready:
                    updates["ready_manual_override_at"] = None

        if updates:
            update_turnover(turnover["turnover_id"], actor="system", **updates)
            updated += 1

    return {"updated": updated, "rows_seen": rows_seen}


def backfill_placeholder_ready_dates(
    property_id: int,
    *,
    phase_ids: list[int] | None = None,
) -> dict:
    """Set placeholder report_ready_date on open turnovers where it is NULL.

    For each open turnover with report_ready_date IS NULL and
    ready_manual_override_at IS NULL (no manual override), sets
    report_ready_date = move_out_date + PLACEHOLDER_READY_DATE_OFFSET_DAYS.
    Does NOT set ready_manual_override_at so reports can overwrite freely.

    Idempotent: turnovers that already have a report_ready_date are skipped.

    Returns dict with keys: filled (int), skipped (int).
    """
    check_writes_enabled()
    open_turnovers = turnover_repository.get_open_by_property(
        property_id,
        phase_ids=phase_ids,
    )
    filled = 0
    skipped = 0
    for turnover in open_turnovers:
        if turnover.get("report_ready_date") is not None:
            skipped += 1
            continue
        if turnover.get("ready_manual_override_at") is not None:
            skipped += 1
            continue
        move_out = turnover.get("move_out_date")
        if move_out is None:
            skipped += 1
            continue
        turnover_id = turnover["turnover_id"]
        placeholder_ready = move_out + timedelta(days=PLACEHOLDER_READY_DATE_OFFSET_DAYS)
        try:
            turnover_repository.update(turnover_id, report_ready_date=placeholder_ready)
            audit_repository.insert(
                property_id=property_id,
                entity_type="turnover",
                entity_id=turnover_id,
                field_name="report_ready_date",
                old_value=None,
                new_value=str(placeholder_ready),
                actor="system",
                source="turnover_service.placeholder",
            )
            filled += 1
        except Exception:
            logger.exception(
                "Failed to backfill placeholder ready date for turnover %s", turnover_id
            )
            skipped += 1
    return {"filled": filled, "skipped": skipped}


def search_unit(property_id: int, raw_code: str) -> dict | None:
    """Look up a unit by raw code after normalization."""
    norm = normalize_unit_code(raw_code)
    if not norm:
        return None
    return unit_repository.get_by_code_norm(property_id, norm)


def get_open_turnover_for_unit(unit_id: int) -> dict | None:
    """Return the open turnover for a unit, or None."""
    return turnover_repository.get_open_by_unit(unit_id)


def get_turnover_detail(turnover_id: int) -> dict | None:
    turnover = turnover_repository.get_by_id(turnover_id)
    if turnover is None:
        return None
    turnover["lifecycle_phase"] = turnover_lifecycle.lifecycle_phase(turnover)
    turnover["days_since_move_out"] = turnover_lifecycle.days_since_move_out(turnover)
    turnover["days_to_move_in"] = turnover_lifecycle.days_to_move_in(turnover)
    turnover["vacancy_days"] = turnover_lifecycle.vacancy_days(turnover)
    return turnover


# ── W/D workflow helpers ──────────────────────────────────────────────────────


def mark_wd_notified(turnover_id: int, actor: str = "manager") -> dict:
    """Record that the W/D unit has been notified. Idempotent."""
    existing = turnover_repository.get_by_id(turnover_id)
    if existing is None:
        raise TurnoverError(f"Turnover {turnover_id} not found.")
    if existing.get("wd_notified_at") is not None:
        return existing
    return update_turnover(turnover_id, actor=actor, wd_notified_at=datetime.utcnow())


def mark_wd_installed(turnover_id: int, actor: str = "manager") -> dict:
    """Record that the W/D unit has been installed. Requires notified first."""
    existing = turnover_repository.get_by_id(turnover_id)
    if existing is None:
        raise TurnoverError(f"Turnover {turnover_id} not found.")
    if existing.get("wd_notified_at") is None:
        raise TurnoverError("Cannot mark installed: W/D has not been marked as notified.")
    if existing.get("wd_installed_at") is not None:
        return existing
    return update_turnover(turnover_id, actor=actor, wd_installed_at=datetime.utcnow())


def undo_wd_notified(turnover_id: int, actor: str = "manager") -> dict:
    """Clear wd_notified_at. Blocked if wd_installed_at is set."""
    existing = turnover_repository.get_by_id(turnover_id)
    if existing is None:
        raise TurnoverError(f"Turnover {turnover_id} not found.")
    if existing.get("wd_installed_at") is not None:
        raise TurnoverError(
            "Cannot undo notified: W/D is already marked installed. Undo installed first."
        )
    if existing.get("wd_notified_at") is None:
        return existing
    return update_turnover(turnover_id, actor=actor, wd_notified_at=None)


def undo_wd_installed(turnover_id: int, actor: str = "manager") -> dict:
    """Clear wd_installed_at. Idempotent."""
    existing = turnover_repository.get_by_id(turnover_id)
    if existing is None:
        raise TurnoverError(f"Turnover {turnover_id} not found.")
    if existing.get("wd_installed_at") is None:
        return existing
    return update_turnover(turnover_id, actor=actor, wd_installed_at=None)

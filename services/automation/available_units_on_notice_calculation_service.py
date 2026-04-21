"""Available Units On Notice calculation service.

Processes On Notice rows from Available Units import data to determine
operational state before data reaches the board:

- If available_date <= today and unit has no open turnover: create turnover
  immediately (Vacant Not Ready, report_ready_date from Move-In Ready Date),
  ensure tasks, audit.
- If available_date is in the future: upsert into unit_on_notice_snapshot
  for midnight automation to process when the date arrives.

Runs (1) after every Available Units import completes, and (2) as part of
run_midnight_automation (from latest import) to catch units whose date
arrived since the last import.

Idempotent: checks for existing turnover before creating; safe to run multiple times.
"""

from __future__ import annotations

import logging
from datetime import date

from domain.availability_status import status_is_on_notice
from domain.unit_identity import normalize_unit_code
from db.repository import (
    audit_repository,
    import_repository,
    turnover_repository,
    unit_on_notice_snapshot_repository,
    unit_repository,
)
from services import turnover_service
from services.imports.common import parse_date
from services.write_guard import check_writes_enabled

logger = logging.getLogger(__name__)

CALCULATION_ACTOR = "system"
CALCULATION_SOURCE = "import automation layer"


def process_on_notice_after_import(
    property_id: int,
    batch_id: int,
    today: date | None = None,
) -> dict:
    """Run On Notice calculation for the given batch (e.g. right after import completes).

    Reads import_row records for the batch, parses raw_json for On Notice rows,
    creates turnovers for units whose available_date has arrived, and upserts
    snapshot for future dates.

    Returns:
        Dict with keys: created (int), snapshot_upserted (int), errors (list[str]).
    """
    check_writes_enabled()
    if today is None:
        today = date.today()

    rows = import_repository.get_rows_by_batch(batch_id)
    return _process_on_notice_rows(property_id, rows, today)


def process_on_notice_from_latest_import(
    property_id: int,
    today: date | None = None,
) -> dict:
    """Run On Notice calculation from the latest completed Available Units batch.

    Used for backfill and as part of midnight automation: finds the latest
    completed AVAILABLE_UNITS batch for the property, loads its rows, and
    runs the same logic as process_on_notice_after_import.

    Returns:
        Dict with keys: created (int), snapshot_upserted (int), errors (list[str]).
    """
    check_writes_enabled()
    if today is None:
        today = date.today()

    batches = import_repository.get_batches_by_property(property_id, limit=200)
    for batch in batches:
        if (
            batch.get("report_type") == "AVAILABLE_UNITS"
            and batch.get("status") == "COMPLETED"
        ):
            rows = import_repository.get_rows_by_batch(batch["batch_id"])
            return _process_on_notice_rows(property_id, rows, today)

    return {"created": 0, "snapshot_upserted": 0, "errors": []}


def process_on_notice_from_latest_import_all_properties(
    today: date | None = None,
) -> dict:
    """Run On Notice calculation from latest import for every property.

    Used by run_midnight_automation. Returns aggregated created, snapshot_upserted,
    and errors.
    """
    from db.repository import property_repository

    if today is None:
        today = date.today()

    properties = property_repository.get_all()
    total_created = 0
    total_snapshot_upserted = 0
    all_errors: list[str] = []

    for prop in properties:
        pid = prop["property_id"]
        result = process_on_notice_from_latest_import(property_id=pid, today=today)
        total_created += result["created"]
        total_snapshot_upserted += result["snapshot_upserted"]
        for err in result["errors"]:
            all_errors.append(f"property_id={pid}: {err}")

    return {
        "total_created": total_created,
        "total_snapshot_upserted": total_snapshot_upserted,
        "errors": all_errors,
    }


def _process_on_notice_rows(
    property_id: int,
    rows: list[dict],
    today: date,
) -> dict:
    """Core logic: for each On Notice row, create turnover if due else upsert snapshot."""
    created = 0
    snapshot_upserted = 0
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

        if available_date is None:
            continue

        unit = unit_repository.get_by_code_norm(property_id, unit_norm)
        if unit is None:
            continue

        unit_id = unit["unit_id"]
        existing_turnover = turnover_repository.get_open_by_unit(unit_id)
        if existing_turnover is not None:
            continue

        if available_date <= today:
            try:
                turnover = turnover_service.create_turnover(
                    property_id=property_id,
                    unit_id=unit_id,
                    move_out_date=available_date,
                    actor=CALCULATION_ACTOR,
                )
                turnover_id = turnover["turnover_id"]
                initial_fields: dict = {
                    "availability_status": "vacant not ready",
                    "manual_ready_status": "Vacant Not Ready",
                    "available_date": available_date,
                }
                if move_in_ready_date is not None:
                    initial_fields["report_ready_date"] = move_in_ready_date
                turnover_service.update_turnover(
                    turnover_id,
                    actor=CALCULATION_ACTOR,
                    **initial_fields,
                )
                audit_repository.insert(
                    property_id=property_id,
                    entity_type="turnover",
                    entity_id=turnover_id,
                    field_name="lifecycle_transition",
                    old_value=None,
                    new_value="turnover_created_by_import_automation_layer_from_available_units_calculation",
                    actor=CALCULATION_ACTOR,
                    source=CALCULATION_SOURCE,
                )
                created += 1
            except turnover_service.TurnoverError as exc:
                err = f"unit_id={unit_id}: {exc}"
                errors.append(err)
                logger.warning("On-notice calculation: %s", err)
            except Exception as exc:
                err = f"unit_id={unit_id}: {exc}"
                errors.append(err)
                logger.exception("On-notice calculation failed for unit %s", unit_id)
        else:
            unit_on_notice_snapshot_repository.upsert(
                property_id=property_id,
                unit_id=unit_id,
                available_date=available_date,
                move_in_ready_date=move_in_ready_date,
            )
            snapshot_upserted += 1

    return {
        "created": created,
        "snapshot_upserted": snapshot_upserted,
        "errors": errors,
    }

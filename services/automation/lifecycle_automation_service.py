"""Lifecycle automation service — Import Automation Layer (Phase 5).

Runs once daily (e.g. at midnight). Two paths:
1. Open turnovers still in "On Notice" whose available_date has arrived → transition
   to "Vacant Not Ready", ensure tasks, audit.
2. Units in unit_on_notice_snapshot (no turnover) with available_date <= today →
   create turnover (Vacant not ready), ensure tasks, audit, remove from snapshot.

Callable by a cron job or external scheduler.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from db.repository import (
    audit_repository,
    turnover_repository,
    unit_on_notice_snapshot_repository,
)
from services import turnover_service

logger = logging.getLogger(__name__)

AUTOMATION_SOURCE = "import automation layer"
AUTOMATION_ACTOR = "system"
AUTO_TRANSITION_MAX_DV = 10


def run_available_date_transition(
    property_id: int,
    today: date | None = None,
    phase_ids: list[int] | None = None,
) -> dict:
    """Auto-transition On Notice turnovers to Vacant Not Ready when DV is 0..10.

    Finds open turnovers where:
      - manual_ready_status == 'On Notice'
      - move_out_date <= today (DV >= 0)
      - (today - move_out_date).days <= AUTO_TRANSITION_MAX_DV (catch-up window)

    Sets status_manual_override_at so the user owns the status field afterward.
    Idempotent: once transitioned the turnover is no longer On Notice.

    Args:
        property_id: Property to process.
        today: Reference date (default: date.today()).
        phase_ids: Optional phase scope; if None, all open turnovers for property.

    Returns:
        Dict with keys: transitioned (int), errors (list of str).
    """
    if today is None:
        today = date.today()

    open_turnovers = turnover_repository.get_open_by_property(
        property_id,
        phase_ids=phase_ids,
    )

    eligible = [
        t
        for t in open_turnovers
        if t.get("manual_ready_status") == "On Notice"
        and t.get("move_out_date") is not None
        and t["move_out_date"] <= today
        and (today - t["move_out_date"]).days <= AUTO_TRANSITION_MAX_DV
    ]

    transitioned = 0
    errors: list[str] = []

    for turnover in eligible:
        turnover_id = turnover["turnover_id"]
        try:
            turnover_service.update_turnover(
                turnover_id,
                actor=AUTOMATION_ACTOR,
                manual_ready_status="Vacant Not Ready",
                availability_status="vacant not ready",
                status_manual_override_at=datetime.now(tz=timezone.utc),
            )
            audit_repository.insert(
                property_id=property_id,
                entity_type="turnover",
                entity_id=turnover_id,
                field_name="lifecycle_transition",
                old_value="On Notice",
                new_value="On Notice → Vacant Not Ready by import automation layer",
                actor=AUTOMATION_ACTOR,
                source=AUTOMATION_SOURCE,
            )
            transitioned += 1
        except turnover_service.TurnoverError as exc:
            errors.append(f"turnover_id={turnover_id}: {exc}")
            logger.warning("Available-date transition failed for turnover %s: %s", turnover_id, exc)
        except Exception as exc:
            errors.append(f"turnover_id={turnover_id}: {exc}")
            logger.exception("Available-date transition failed for turnover %s", turnover_id)

    return {"transitioned": transitioned, "errors": errors}


def run_available_date_transition_all_properties(
    today: date | None = None,
) -> dict:
    """Run available-date transition for all properties.

    Intended for a single daily cron job. Uses property_repository.get_all()
    and calls run_available_date_transition for each property.

    Returns:
        Dict with keys: total_transitioned (int), by_property (dict[property_id, result]), errors (list).
    """
    from db.repository import property_repository

    if today is None:
        today = date.today()

    properties = property_repository.get_all()
    total_transitioned = 0
    by_property: dict[int, dict] = {}
    all_errors: list[str] = []

    for prop in properties:
        pid = prop["property_id"]
        result = run_available_date_transition(property_id=pid, today=today)
        by_property[pid] = result
        total_transitioned += result["transitioned"]
        for err in result["errors"]:
            all_errors.append(f"property_id={pid}: {err}")

    return {
        "total_transitioned": total_transitioned,
        "by_property": by_property,
        "errors": all_errors,
    }


def run_on_notice_turnover_creation(
    property_id: int,
    today: date | None = None,
) -> dict:
    """Create turnovers for units in unit_on_notice_snapshot when available_date <= today.

    Safety: only units with no open turnover are processed. For each: create turnover
    (move_out_date=available_date), set availability_status and manual_ready_status to
    Vacant not ready, set report_ready_date from snapshot if present, ensure tasks,
    audit, then remove from snapshot.

    Returns:
        Dict with keys: created (int), errors (list of str).
    """
    if today is None:
        today = date.today()

    rows = unit_on_notice_snapshot_repository.get_eligible_for_automation(
        property_id, today
    )
    created = 0
    errors: list[str] = []

    for row in rows:
        unit_id = row["unit_id"]
        available_date = row["available_date"]
        move_in_ready_date = row.get("move_in_ready_date")

        existing = turnover_repository.get_open_by_unit(unit_id)
        if existing is not None:
            continue

        try:
            turnover = turnover_service.create_turnover(
                property_id=property_id,
                unit_id=unit_id,
                move_out_date=available_date,
                actor=AUTOMATION_ACTOR,
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
                actor=AUTOMATION_ACTOR,
                **initial_fields,
            )
            audit_repository.insert(
                property_id=property_id,
                entity_type="turnover",
                entity_id=turnover_id,
                field_name="lifecycle_transition",
                old_value=None,
                new_value="turnover_created_by_import_automation_layer_from_on_notice_snapshot",
                actor=AUTOMATION_ACTOR,
                source=AUTOMATION_SOURCE,
            )
            unit_on_notice_snapshot_repository.delete_by_unit(property_id, unit_id)
            created += 1
        except turnover_service.TurnoverError as exc:
            errors.append(f"unit_id={unit_id}: {exc}")
            logger.warning(
                "On-notice turnover creation failed for unit %s: %s", unit_id, exc
            )
        except Exception as exc:
            errors.append(f"unit_id={unit_id}: {exc}")
            logger.exception(
                "On-notice turnover creation failed for unit %s", unit_id
            )

    return {"created": created, "errors": errors}


def run_on_notice_turnover_creation_all_properties(
    today: date | None = None,
) -> dict:
    """Run on-notice turnover creation for all properties.

    Returns:
        Dict with keys: total_created (int), by_property (dict), errors (list).
    """
    from db.repository import property_repository

    if today is None:
        today = date.today()

    properties = property_repository.get_all()
    total_created = 0
    by_property: dict[int, dict] = {}
    all_errors: list[str] = []

    for prop in properties:
        pid = prop["property_id"]
        result = run_on_notice_turnover_creation(property_id=pid, today=today)
        by_property[pid] = result
        total_created += result["created"]
        for err in result["errors"]:
            all_errors.append(f"property_id={pid}: {err}")

    return {
        "total_created": total_created,
        "by_property": by_property,
        "errors": all_errors,
    }


def run_midnight_automation(today: date | None = None) -> dict:
    """Run the Import Automation Layer (e.g. from cron at midnight).

    Executes both auto-transition (On Notice → Vacant Not Ready) and
    on-notice turnover creation from snapshots for all properties.
    """
    if today is None:
        today = date.today()

    transitions = run_available_date_transition_all_properties(today=today)
    on_notice_created = run_on_notice_turnover_creation_all_properties(today=today)

    all_errors = transitions["errors"] + on_notice_created["errors"]

    return {
        "today": today.isoformat(),
        "on_notice_from_import": {
            "total_created": 0,
            "total_snapshot_upserted": 0,
        },
        "transitions": transitions,
        "on_notice_created": on_notice_created,
        "errors": all_errors,
    }

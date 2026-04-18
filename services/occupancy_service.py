"""Occupancy service — load and manage move-in dates in unit_occupancy_global.

Core design: the ingest() function is source-agnostic. It accepts plain
[{"unit_number": str, "move_in_date": date}] records from any source.

Adding a new data source only requires:
  1. Transform source data into that record shape.
  2. Call occupancy_service.ingest(property_id, records).

No changes needed in the repository, validator, or output layer.
"""

from __future__ import annotations

import logging
from datetime import date

from db.repository import occupancy_repository, unit_repository
from domain.unit_identity import normalize_unit_code
from services.parsers import resident_activity_parser

logger = logging.getLogger(__name__)


def ingest(property_id: int, records: list[dict]) -> dict:
    """Core ingestion entry point — source-agnostic.

    Args:
        property_id: The property to scope all writes to.
        records: List of dicts with keys "unit_number" (str) and
                 "move_in_date" (date). No other fields required.

    Returns:
        {"processed": int, "matched": int, "unresolved": int}
    """
    processed = len(records)
    matched = 0
    unresolved = 0

    for rec in records:
        raw_unit = rec.get("unit_number", "")
        move_in: date | None = rec.get("move_in_date")

        if not raw_unit:
            unresolved += 1
            continue

        unit_norm = normalize_unit_code(raw_unit)
        unit_row = unit_repository.get_by_code_norm(property_id, unit_norm)

        if unit_row is None:
            logger.debug(
                "occupancy_service.ingest: unit '%s' (norm: '%s') not found for property %d",
                raw_unit, unit_norm, property_id,
            )
            unresolved += 1
            continue

        occupancy_repository.upsert(property_id, unit_row["unit_id"], move_in)
        matched += 1

    logger.info(
        "occupancy_service.ingest: property=%d processed=%d matched=%d unresolved=%d",
        property_id, processed, matched, unresolved,
    )
    return {"processed": processed, "matched": matched, "unresolved": unresolved}


def ingest_resident_activity(
    property_id: int,
    file_content: bytes,
    filename: str = "resident_activity.xls",
) -> dict:
    """Parse a Resident Activity file and ingest move-in dates.

    Handles de-duplication: prefers "Current resident" rows; when multiple
    current residents exist for the same unit, uses the latest move_in_date.

    Returns:
        {"processed": int, "matched": int, "unresolved": int}
        (counts apply after de-duplication)
    """
    raw_records = resident_activity_parser.parse(file_content, filename)

    # De-duplicate per unit: prefer current residents, latest date wins
    by_unit: dict[str, dict] = {}
    for rec in raw_records:
        key = rec["unit_number"]
        status = rec.get("resident_status", "")
        existing = by_unit.get(key)

        if existing is None:
            by_unit[key] = rec
            continue

        existing_status = existing.get("resident_status", "")
        is_current = status == "Current resident"
        existing_is_current = existing_status == "Current resident"

        if is_current and not existing_is_current:
            # Upgrade to current resident
            by_unit[key] = rec
        elif is_current == existing_is_current:
            # Same priority — keep the most recent move-in date
            if rec["move_in_date"] > existing["move_in_date"]:
                by_unit[key] = rec

    # Strip resident_status before handing to the generic ingest core
    clean_records = [
        {"unit_number": r["unit_number"], "move_in_date": r["move_in_date"]}
        for r in by_unit.values()
    ]

    logger.info(
        "occupancy_service.ingest_resident_activity: %d raw records → %d after de-duplication",
        len(raw_records), len(clean_records),
    )
    return ingest(property_id, clean_records)


def get_all_occupancy(property_id: int) -> dict[int, date | None]:
    """Return {unit_id: move_in_date} for all loaded units in this property."""
    return occupancy_repository.get_all_by_property(property_id)


def get_occupancy_status(property_id: int) -> dict:
    """Return summary info for the UI status display.

    Returns:
        {"unit_count": int, "last_updated": date | None}
    """
    return {
        "unit_count": occupancy_repository.count_by_property(property_id),
        "last_updated": occupancy_repository.get_last_updated(property_id),
    }

"""Import Diagnostics service.

Provides read-only visibility into import batches and their row-level
outcomes so managers can inspect what each report import did.
"""

from __future__ import annotations

from db.repository import import_repository


def list_import_batches(property_id: int, limit: int = 50) -> list[dict]:
    """Return recent import batches with aggregated outcome counts."""
    return import_repository.get_import_batches(property_id, limit=limit)


def get_batch_details(batch_id: int) -> list[dict]:
    """Return row-level results for a single batch.

    Each dict contains: unit, validation_status, conflict_reason,
    move_out_date, move_in_date, and raw_json (which may hold
    available_date / ready_date depending on report type).
    """
    return import_repository.get_import_rows(batch_id)

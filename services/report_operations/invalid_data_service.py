"""Invalid Data resolution service.

Provides the operational queue for import rows marked INVALID because
required data was missing or malformed.  The manager supplies corrected
values; the service applies them to the appropriate turnover and marks
the import row resolved.
"""

from __future__ import annotations

import logging

from db.repository import audit_repository, import_repository
from services import turnover_service
from services.write_guard import check_writes_enabled

logger = logging.getLogger(__name__)

# Maps report_type to the turnover field the correction targets.
_REPORT_FIELD_MAP: dict[str, str] = {
    "MOVE_OUTS": "move_out_date",
    "PENDING_MOVE_INS": "move_in_date",
    "AVAILABLE_UNITS": "available_date",
    "PENDING_FAS": "confirmed_move_out_date",
}


def list_invalid_rows(property_id: int) -> list[dict]:
    """Return unresolved INVALID import rows for the queue.

    Each dict is enriched with a human-readable ``reason`` derived from
    ``conflict_reason`` or the report type.
    """
    raw = import_repository.get_invalid_import_rows(property_id)

    enriched: list[dict] = []
    for r in raw:
        reason = r.get("conflict_reason") or _default_reason(r.get("report_type"))
        enriched.append(
            {
                "row_id": r["row_id"],
                "unit": r.get("unit") or "—",
                "batch_id": r["batch_id"],
                "report_type": r["report_type"],
                "reason": reason,
                "move_out_date": r.get("move_out_date"),
                "move_in_date": r.get("move_in_date"),
                "raw_json": r.get("raw_json"),
                "detected_at": r["detected_at"],
            }
        )
    return enriched


def resolve_invalid_row(
    row_id: int,
    corrected_fields: dict,
    *,
    property_id: int,
    actor: str = "manager",
) -> None:
    """Apply corrected values and mark the INVALID row resolved.

    Parameters
    ----------
    corrected_fields : dict
        Keys are turnover column names (``move_out_date``, ``move_in_date``,
        ``available_date``, etc.) and values are the corrected data.
    """
    check_writes_enabled()

    unit_code = corrected_fields.pop("unit_code_norm", None)
    if not corrected_fields:
        raise ValueError("No corrected fields provided.")

    # Find the turnover to update
    if unit_code:
        unit = turnover_service.search_unit(property_id, unit_code)
        if unit is None:
            raise ValueError(f"Unit '{unit_code}' not found.")
        turnover = turnover_service.get_open_turnover_for_unit(unit["unit_id"])
        if turnover is None:
            raise ValueError(f"No open turnover for unit '{unit_code}'.")
        turnover_service.update_turnover(
            turnover["turnover_id"],
            actor=actor,
            **corrected_fields,
        )

        audit_repository.insert(
            property_id=property_id,
            entity_type="turnover",
            entity_id=turnover["turnover_id"],
            field_name="invalid_data_correction",
            old_value=None,
            new_value=str(corrected_fields),
            actor=actor,
            source="invalid_data_service",
        )

    import_repository.resolve_import_row(row_id)


def _default_reason(report_type: str | None) -> str:
    """Derive a display reason from the report type when conflict_reason is NULL."""
    reasons = {
        "MOVE_OUTS": "Missing move-out date",
        "PENDING_MOVE_INS": "Missing move-in date",
        "AVAILABLE_UNITS": "Missing available date",
        "PENDING_FAS": "Missing FAS date",
    }
    return reasons.get(report_type or "", "Invalid data")

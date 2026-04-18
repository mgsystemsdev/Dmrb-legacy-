"""Override Conflict resolution service.

Provides the operational queue for import rows where a field update was
skipped because a manual override was active and the report value differed.

The manager can either keep the manual value (mark resolved, no changes)
or accept the report value (apply it to the turnover, clear the override,
mark resolved).
"""

from __future__ import annotations

import logging

from db.repository import import_repository, turnover_repository, audit_repository
from services.write_guard import check_writes_enabled

logger = logging.getLogger(__name__)

# Maps the audit-log field_name to the turnover column and its override column.
_FIELD_MAP: dict[str, tuple[str, str]] = {
    "scheduled_move_out_date": ("scheduled_move_out_date", "move_out_manual_override_at"),
    "move_in_date": ("move_in_date", "move_in_manual_override_at"),
    "report_ready_date": ("report_ready_date", "ready_manual_override_at"),
    "availability_status": ("availability_status", "status_manual_override_at"),
}


def list_override_conflicts(property_id: int) -> list[dict]:
    """Return unresolved override-conflict rows with current manual values.

    Each dict contains:
        unit, batch_id, detected_at, conflict_field,
        manual_value (current turnover value), report_value
    """
    raw_rows = import_repository.get_override_conflicts(property_id)

    enriched: list[dict] = []
    for r in raw_rows:
        field = r["conflict_field"]
        turnover_col, _ = _FIELD_MAP.get(field, (field, None))

        # Fetch the current turnover value for context
        turnover = turnover_repository.get_by_id(r["turnover_id"])
        manual_value = None
        if turnover is not None:
            raw = turnover.get(turnover_col)
            manual_value = str(raw) if raw is not None else None

        enriched.append({
            "row_id": r["row_id"],
            "turnover_id": r["turnover_id"],
            "unit": r["unit_code_norm"],
            "batch_id": r["batch_id"],
            "report_type": r["report_type"],
            "detected_at": r["detected_at"],
            "conflict_field": field,
            "manual_value": manual_value,
            "report_value": r["report_value"],
        })

    return enriched


def resolve_override_conflict(
    row_id: int,
    turnover_id: int,
    conflict_field: str,
    action: str,
    *,
    report_value: str | None = None,
    property_id: int | None = None,
    actor: str = "manager",
) -> None:
    """Resolve a single override conflict.

    Parameters
    ----------
    action : str
        ``"keep_manual"`` — mark resolved, no field changes.
        ``"accept_report"`` — apply report value, clear override, mark resolved.
    """
    check_writes_enabled()

    if action not in ("keep_manual", "accept_report"):
        raise ValueError(f"Invalid action: {action!r}")

    if action == "accept_report":
        mapping = _FIELD_MAP.get(conflict_field)
        if mapping is None:
            raise ValueError(f"Unknown conflict field: {conflict_field!r}")

        turnover_col, override_col = mapping
        updates = {
            turnover_col: report_value,
            override_col: None,
        }
        turnover_repository.update(turnover_id, **updates)

        if property_id is not None:
            audit_repository.insert(
                property_id=property_id,
                entity_type="turnover",
                entity_id=turnover_id,
                field_name=turnover_col,
                old_value=None,
                new_value=str(report_value),
                actor=actor,
                source="override_conflict_service:accept_report",
            )

    import_repository.resolve_import_row(row_id)

"""Shared helpers for the import pipeline services.

No business branching — only data transformation and persistence wrappers.
"""

from __future__ import annotations

from datetime import date, datetime

from db.repository import unit_repository
from domain import import_outcomes
from domain.unit_identity import compose_identity_key, normalize_unit_code, parse_unit_parts
from services import import_service, property_service


def normalize_unit(unit_str: str) -> str:
    """Normalize a raw unit string via the domain rule."""
    return normalize_unit_code(unit_str)


def parse_date(value) -> date | None:
    """Safely parse a value into a ``date``.

    Accepts ``date``, ``datetime``, ISO-format strings (``YYYY-MM-DD`` or
    ``MM/DD/YYYY``), and ``None``.  Returns ``None`` when parsing fails.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw = str(value).strip()
    if not raw:
        return None

    # ISO format: YYYY-MM-DD
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _sanitize_row_data(row_data: dict) -> dict:
    """Replace NaN / Inf values with None so the dict is valid JSON."""
    import math

    clean: dict = {}
    for k, v in row_data.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            clean[k] = None
        else:
            clean[k] = v
    return clean


# Invariant 3: every parsed row must produce exactly one import_row. Each branch
# in the apply loop must call write_import_row() exactly once; no continue may
# skip it. status must be one of: OK, CONFLICT, INVALID, IGNORED, SKIPPED_OVERRIDE
# (see domain.import_outcomes and import_row.validation_status constraint).
def write_import_row(
    property_id: int,
    batch_id: int,
    row_data: dict,
    status: str,
    *,
    reason: str | None = None,
    unit_code_raw: str | None = None,
    unit_code_norm: str | None = None,
    move_out_date: date | None = None,
    move_in_date: date | None = None,
) -> dict:
    """Persist a single import row via ``import_service.record_row``."""
    row_data = _sanitize_row_data(row_data)
    conflict_flag = status in (
        import_outcomes.CONFLICT,
        import_outcomes.SKIPPED_OVERRIDE,
    )
    # Schema constraint: conflict_reason requires conflict_flag = TRUE.
    effective_reason = reason if conflict_flag else None

    return import_service.record_row(
        property_id=property_id,
        batch_id=batch_id,
        raw_json=row_data,
        validation_status=status,
        unit_code_raw=unit_code_raw,
        unit_code_norm=unit_code_norm,
        move_out_date=move_out_date,
        move_in_date=move_in_date,
        conflict_flag=conflict_flag,
        conflict_reason=effective_reason,
    )


def resolve_or_create_unit(
    property_id: int,
    unit_raw: str,
    unit_norm: str,
) -> dict:
    """Look up unit by normalized code; create with phase/building if needed."""
    unit = unit_repository.get_by_code_norm(property_id, unit_norm)
    if unit is not None:
        return unit

    parts = parse_unit_parts(unit_norm)
    phase_id = None
    building_id = None

    if parts["phase_code"]:
        phase = property_service.get_phase_by_code(property_id, parts["phase_code"])
        if phase is None:
            phase = property_service.create_phase(property_id, parts["phase_code"])
        phase_id = phase["phase_id"]

        if parts["building_code"]:
            building = property_service.get_building_by_code(phase_id, parts["building_code"])
            if building is None:
                building = property_service.create_building(
                    property_id,
                    phase_id,
                    parts["building_code"],
                )
            building_id = building["building_id"]

    identity_key = compose_identity_key(property_id, unit_norm)
    return unit_repository.insert(
        property_id=property_id,
        unit_code_raw=unit_raw,
        unit_code_norm=unit_norm,
        unit_identity_key=identity_key,
        phase_id=phase_id,
        building_id=building_id,
    )


def to_iso_date(d: date | None) -> str | None:
    """Convert a ``date`` to an ISO string, or return ``None``."""
    if d is None:
        return None
    return d.isoformat()

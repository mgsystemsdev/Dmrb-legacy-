"""Pending FAS report apply service.

Iterates parsed rows and records import outcomes.
Business logic (legal confirmation, SLA reconciliation) will be added
in a later phase.
"""

from __future__ import annotations

import logging

from domain import import_outcomes
from services.imports import common

logger = logging.getLogger(__name__)


def apply(
    batch_id: int,
    rows: list[dict],
    property_id: int,
) -> dict:
    """Process Pending FAS rows and record outcomes.

    Returns counters: ``{applied, conflict, invalid}``.
    """
    applied = 0
    conflict = 0
    invalid = 0

    for row in rows:
        unit_raw = str(row.get("Unit", ""))
        unit_norm = common.normalize_unit(unit_raw) if unit_raw else None
        mo_date = common.parse_date(row.get("MO / Cancel Date"))

        # Placeholder: record every row as OK
        status = import_outcomes.OK
        reason = None

        common.write_import_row(
            property_id=property_id,
            batch_id=batch_id,
            row_data=row,
            status=status,
            reason=reason,
            unit_code_raw=unit_raw,
            unit_code_norm=unit_norm,
            move_out_date=mo_date,
        )

        if status == import_outcomes.OK:
            applied += 1
        elif status == import_outcomes.CONFLICT:
            conflict += 1
        elif status == import_outcomes.INVALID:
            invalid += 1

    return {"applied": applied, "conflict": conflict, "invalid": invalid}

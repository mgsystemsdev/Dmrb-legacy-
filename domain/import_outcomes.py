"""Import row outcome classification.

Pure constants and helpers — no database access, no Streamlit imports.

Every imported row receives a status and an optional reason that explain
what happened during processing.
"""

from __future__ import annotations

# ── Row Outcome Statuses ─────────────────────────────────────────────────────

OK = "OK"
INVALID = "INVALID"
CONFLICT = "CONFLICT"
IGNORED = "IGNORED"
SKIPPED_OVERRIDE = "SKIPPED_OVERRIDE"


# ── Conflict / Ignore Reasons ────────────────────────────────────────────────

MOVE_IN_WITHOUT_OPEN_TURNOVER = "MOVE_IN_WITHOUT_OPEN_TURNOVER"
NO_OPEN_TURNOVER_FOR_READY_DATE = "NO_OPEN_TURNOVER_FOR_READY_DATE"
NO_OPEN_TURNOVER_FOR_VALIDATION = "NO_OPEN_TURNOVER_FOR_VALIDATION"
MISSING_MOVE_OUT_DATE = "MISSING_MOVE_OUT_DATE"
MISSING_MOVE_IN_DATE = "MISSING_MOVE_IN_DATE"
MISSING_AVAILABLE_DATE = "MISSING_AVAILABLE_DATE"
CREATED_TURNOVER_FROM_AVAILABILITY = "CREATED_TURNOVER_FROM_AVAILABILITY"
ON_NOTICE_PENDING_AVAILABLE_DATE = "ON_NOTICE_PENDING_AVAILABLE_DATE"
IMPORT_SKIPPED_DUE_TO_MANUAL_OVERRIDE = "IMPORT_SKIPPED_DUE_TO_MANUAL_OVERRIDE"
PARTIAL_OVERRIDE_SKIP = "PARTIAL_OVERRIDE_SKIP"
UNIT_NOT_IN_VALID_PHASE = "UNIT_NOT_IN_VALID_PHASE"


def classify_row_outcome(
    *,
    has_open_turnover: bool = False,
    has_required_fields: bool = True,
    override_skipped: bool = False,
    reason: str | None = None,
) -> tuple[str, str | None]:
    """Return ``(status, reason)`` for an import row.

    This is a minimal classifier that services can call to keep outcome
    logic in the domain layer.  More specific classification can be added
    as needed.
    """
    if override_skipped:
        return (SKIPPED_OVERRIDE, reason or IMPORT_SKIPPED_DUE_TO_MANUAL_OVERRIDE)

    if not has_required_fields:
        return (INVALID, reason)

    if not has_open_turnover:
        return (CONFLICT, reason)

    return (OK, reason)

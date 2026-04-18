"""Availability status semantics.

Pure function — no database access, no Streamlit imports.

Determines which availability statuses allow the creation of a new
turnover when no open turnover exists for a unit.

Also provides effective status: when stored status is On Notice and
available_date has passed, the unit is treated as Vacant Not Ready
for all operational purposes (lifecycle, SLA, agreements). The
report remains source of truth for stored data; this is a computed override.
"""

from __future__ import annotations

from datetime import date


_STATUSES_ALLOWING_CREATION: set[str] = {
    "vacant ready",
    "vacant not ready",
    "beacon ready",
    "beacon not ready",
}

_VACANT_STATUSES: set[str] = {
    "vacant ready",
    "vacant not ready",
}

_ON_NOTICE_STATUSES: set[str] = {
    "on notice",
    "on notice (break)",
}

# Canonical manual_ready_status values (schema constraint).
MANUAL_READY_ON_NOTICE = "On Notice"
MANUAL_READY_VACANT_NOT_READY = "Vacant Not Ready"
MANUAL_READY_VACANT_READY = "Vacant Ready"

# Map normalized availability_status (from import) to canonical manual_ready_status.
_AVAILABILITY_TO_MANUAL_READY: dict[str, str] = {
    "on notice": MANUAL_READY_ON_NOTICE,
    "on notice (break)": MANUAL_READY_ON_NOTICE,
    "vacant not ready": MANUAL_READY_VACANT_NOT_READY,
    "beacon not ready": MANUAL_READY_VACANT_NOT_READY,
    "vacant ready": MANUAL_READY_VACANT_READY,
    "beacon ready": MANUAL_READY_VACANT_READY,
}


def status_allows_turnover_creation(status: str) -> bool:
    """Return ``True`` if *status* permits creating a new turnover.

    The check is case-insensitive.
    """
    return status.strip().lower() in _STATUSES_ALLOWING_CREATION


def status_is_vacant(status: str | None) -> bool:
    """Return ``True`` if *status* represents a vacant unit."""
    return (status or "").strip().lower() in _VACANT_STATUSES


def status_is_on_notice(status: str | None) -> bool:
    """Return ``True`` if *status* represents an on-notice unit (e.g. resident gave notice)."""
    return (status or "").strip().lower() in _ON_NOTICE_STATUSES


def effective_manual_ready_status(turnover: dict, today: date | None = None) -> str | None:
    """Return the operational manual_ready_status for a turnover.

    Only overrides when stored is exactly On Notice: if available_date exists and
    is today or in the past, returns Vacant Not Ready. Otherwise returns stored unchanged.
    Vacant Ready, Vacant Not Ready, and any other stored value are never modified.
    When manual_ready_status is None, derives from availability_status so units
    with only availability_status set (e.g. "vacant ready") show correctly.
    """
    stored = turnover.get("manual_ready_status")
    # When not set, derive from availability_status for display/lifecycle consistency.
    if stored is None:
        raw = (turnover.get("availability_status") or "").strip().lower()
        return _AVAILABILITY_TO_MANUAL_READY.get(raw) if raw else None
    # Critical: if stored is not exactly On Notice, return immediately. Do not check available_date.
    if stored != MANUAL_READY_ON_NOTICE:
        return stored
    avail = turnover.get("available_date")
    if avail is None:
        return stored
    today = today or date.today()
    if avail <= today:
        return MANUAL_READY_VACANT_NOT_READY
    return stored


def effective_availability_status(turnover: dict, today: date | None = None) -> str | None:
    """Return the operational availability_status for a turnover (normalized lowercase).

    Only overrides when stored manual_ready_status is On Notice and stored
    availability_status is on notice: if available_date exists and is today or in the past,
    returns 'vacant not ready'. Otherwise returns stored availability_status (normalized).
    Vacant Ready, Vacant Not Ready, and any other stored value are never modified.
    """
    # Critical: only apply override when the unit is actually On Notice (canonical: manual_ready_status).
    if turnover.get("manual_ready_status") != MANUAL_READY_ON_NOTICE:
        stored = (turnover.get("availability_status") or "").strip().lower()
        return stored if stored else None
    stored = (turnover.get("availability_status") or "").strip().lower()
    if not status_is_on_notice(stored):
        return stored if stored else None
    avail = turnover.get("available_date")
    if avail is None:
        return stored
    today = today or date.today()
    if avail <= today:
        return "vacant not ready"
    return stored


def availability_status_to_manual_ready_status(raw_status: str | None) -> str | None:
    """Map normalized availability_status from import to canonical manual_ready_status.

    Returns one of 'On Notice', 'Vacant Not Ready', 'Vacant Ready', or None if no mapping.
    """
    if not raw_status:
        return None
    return _AVAILABILITY_TO_MANUAL_READY.get((raw_status or "").strip().lower())

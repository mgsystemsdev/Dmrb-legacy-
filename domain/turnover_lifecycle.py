"""Turnover lifecycle phase computation.

Pure functions — no database access, no Streamlit imports.
Operates on turnover dicts as returned by turnover_repository.
"""

from __future__ import annotations

from datetime import date

from domain.availability_status import effective_manual_ready_status

# ── Lifecycle Phases ─────────────────────────────────────────────────────────

PHASE_PRE_NOTICE = "PRE_NOTICE"
PHASE_ON_NOTICE = "ON_NOTICE"
PHASE_VACANT_NOT_READY = "VACANT_NOT_READY"
PHASE_VACANT_READY = "VACANT_READY"
PHASE_OCCUPIED = "OCCUPIED"
PHASE_CLOSED = "CLOSED"
PHASE_CANCELED = "CANCELED"

PHASE_ORDER = [
    PHASE_PRE_NOTICE,
    PHASE_ON_NOTICE,
    PHASE_VACANT_NOT_READY,
    PHASE_VACANT_READY,
    PHASE_OCCUPIED,
    PHASE_CLOSED,
    PHASE_CANCELED,
]


class TransitionError(Exception):
    """Raised when a requested lifecycle phase change violates the allowed graph."""


ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    PHASE_PRE_NOTICE: frozenset({PHASE_ON_NOTICE, PHASE_CANCELED}),
    PHASE_ON_NOTICE: frozenset({PHASE_VACANT_NOT_READY, PHASE_CANCELED}),
    PHASE_VACANT_NOT_READY: frozenset({PHASE_VACANT_READY, PHASE_CLOSED, PHASE_CANCELED}),
    PHASE_VACANT_READY: frozenset(
        {PHASE_OCCUPIED, PHASE_VACANT_NOT_READY, PHASE_CLOSED, PHASE_CANCELED}
    ),
    PHASE_OCCUPIED: frozenset({PHASE_CLOSED}),
    PHASE_CLOSED: frozenset(),
    PHASE_CANCELED: frozenset(),
}


def validate_transition(from_phase: str, to_phase: str) -> None:
    """Enforce :data:`ALLOWED_TRANSITIONS`; raise :class:`TransitionError` if disallowed."""
    allowed = ALLOWED_TRANSITIONS.get(from_phase, frozenset())
    if to_phase not in allowed:
        raise TransitionError(
            f"Transition {from_phase} → {to_phase} not allowed. Allowed: {sorted(allowed)}"
        )


def lifecycle_phase(turnover: dict, today: date | None = None) -> str:
    """Derive the current lifecycle phase from turnover state."""
    if turnover.get("canceled_at"):
        return PHASE_CANCELED
    if turnover.get("closed_at"):
        return PHASE_CLOSED
    if turnover.get("move_in_date"):
        today = today or date.today()
        if turnover["move_in_date"] <= today:
            return PHASE_OCCUPIED

    if effective_manual_ready_status(turnover, today) == "Vacant Ready":
        return PHASE_VACANT_READY

    today = today or date.today()
    move_out = turnover["move_out_date"]

    if move_out > today:
        return (
            PHASE_ON_NOTICE
            if effective_manual_ready_status(turnover, today) == "On Notice"
            else PHASE_PRE_NOTICE
        )

    return PHASE_VACANT_NOT_READY


# ── Time Deltas ──────────────────────────────────────────────────────────────


def days_since_move_out(turnover: dict, today: date | None = None) -> int | None:
    """Days elapsed since move-out. Negative means move-out is in the future."""
    move_out = turnover.get("move_out_date")
    if move_out is None:
        return None
    today = today or date.today()
    return (today - move_out).days


def days_to_move_in(turnover: dict, today: date | None = None) -> int | None:
    """Days remaining until move-in. Negative means move-in has passed."""
    move_in = turnover.get("move_in_date")
    if move_in is None:
        return None
    today = today or date.today()
    return (move_in - today).days


def vacancy_days(turnover: dict, today: date | None = None) -> int | None:
    """Total days the unit has been or will be vacant (move-out to move-in)."""
    move_out = turnover.get("move_out_date")
    move_in = turnover.get("move_in_date")
    if move_out is None:
        return None
    if move_in is None:
        today = today or date.today()
        if move_out <= today:
            return (today - move_out).days
        return None
    return (move_in - move_out).days


def turnover_window_days(turnover: dict) -> int | None:
    """Planned window from move-out to move-in."""
    move_out = turnover.get("move_out_date")
    move_in = turnover.get("move_in_date")
    if move_out is None or move_in is None:
        return None
    return (move_in - move_out).days


# ── State Checks ─────────────────────────────────────────────────────────────


def _move_in_date_for_schedule(turnover: dict) -> date | None:
    """Move-in date used for DTBR caps / fallback; ignores legacy pre-1990 sentinels."""
    move_in = turnover.get("move_in_date")
    if move_in is None:
        return None
    if hasattr(move_in, "year") and move_in.year < 1990:
        return None
    return move_in


def days_to_be_ready(
    turnover: dict,
    tasks: list[dict],
    today: date | None = None,
) -> int:
    """Days until ready: move-in countdown when scheduled, vendor due date otherwise.

    When move_in_date is set, returns days until move-in (minimum 0).
    When no move-in is scheduled, returns days until the latest vendor_due_date
    across incomplete tasks (COMPLETE and SKIPPED excluded). Returns 0 when
    there are no incomplete tasks with a due date.
    """
    today = today or date.today()
    move_in = _move_in_date_for_schedule(turnover)
    if move_in is not None:
        return max((move_in - today).days, 0)
    due_dates = [
        t["vendor_due_date"]
        for t in tasks
        if t.get("vendor_due_date") is not None
        and t.get("execution_status") not in ("COMPLETE", "SKIPPED")
    ]
    if not due_dates:
        return 0
    return max((max(due_dates) - today).days, 0)


def is_open(turnover: dict) -> bool:
    return turnover.get("closed_at") is None and turnover.get("canceled_at") is None


def is_vacant(turnover: dict, today: date | None = None) -> bool:
    phase = lifecycle_phase(turnover, today)
    return phase in (PHASE_VACANT_NOT_READY, PHASE_VACANT_READY)


def is_on_notice(turnover: dict, today: date | None = None) -> bool:
    phase = lifecycle_phase(turnover, today)
    return phase in (PHASE_PRE_NOTICE, PHASE_ON_NOTICE)


def nvm_state(turnover: dict, today: date | None = None) -> str:
    """Return the 5-state N/V/M label matching the operational formula.

    Priority (mirrors Excel formula):
      1. Move-In      — move_in_date is set and <= today
      2. SMI          — move_out_date <= today AND move_in_date > today
      3. Vacant       — move_out_date <= today AND no future move_in_date
      4. Notice + SMI — move_out_date > today AND move_in_date > today
      5. Notice       — move_out_date > today AND no future move_in_date
      —               — closed or canceled
    """
    if turnover.get("canceled_at") or turnover.get("closed_at"):
        return "—"

    today = today or date.today()
    move_out = turnover.get("move_out_date")
    move_in = turnover.get("move_in_date")

    # Pre-1990 sentinel values are treated as absent
    if move_in and hasattr(move_in, "year") and move_in.year < 1990:
        move_in = None

    has_future_move_in = bool(move_in and move_in > today)

    if move_in and move_in <= today:
        return "Move-In"

    if move_out:
        if move_out <= today:
            return "SMI" if has_future_move_in else "Vacant"
        else:
            return "Notice + SMI" if has_future_move_in else "Notice"

    return "—"


# ── Effective Date Resolution ────────────────────────────────────────────────


def effective_move_out_date(turnover: dict):
    """Return the best available move-out date for a turnover.

    Priority order:
      1. manual override (``move_out_manual_override_date``)
      2. ``confirmed_move_out_date``
      3. ``scheduled_move_out_date``
      4. ``move_out_date``

    Returns ``None`` when no date is available.
    """
    return (
        turnover.get("move_out_manual_override_date")
        or turnover.get("confirmed_move_out_date")
        or turnover.get("scheduled_move_out_date")
        or turnover.get("move_out_date")
    )

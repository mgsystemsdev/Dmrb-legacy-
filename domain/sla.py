"""SLA breach risk computation.

Pure functions that evaluate whether a turnover is approaching
or has exceeded its SLA window.  No database access.
"""

from __future__ import annotations

from datetime import date


# ── Defaults ─────────────────────────────────────────────────────────────────

DEFAULT_SLA_THRESHOLD_DAYS = 14
WARNING_THRESHOLD_RATIO = 0.75


# ── SLA Risk Levels ──────────────────────────────────────────────────────────

SLA_OK = "OK"
SLA_WARNING = "WARNING"
SLA_BREACH = "BREACH"


def sla_risk(
    turnover: dict,
    today: date | None = None,
    threshold_days: int = DEFAULT_SLA_THRESHOLD_DAYS,
) -> str:
    """Evaluate SLA risk for an open turnover.

    Risk is measured as elapsed vacancy days against the threshold.

    Returns:
        SLA_OK      — within safe window
        SLA_WARNING — past 75 % of threshold
        SLA_BREACH  — at or past threshold
    """
    move_out = turnover.get("move_out_date")
    if move_out is None:
        return SLA_OK

    if turnover.get("closed_at") or turnover.get("canceled_at"):
        return SLA_OK

    today = today or date.today()
    elapsed = (today - move_out).days

    if elapsed < 0:
        return SLA_OK
    if elapsed >= threshold_days:
        return SLA_BREACH

    warning_at = int(threshold_days * WARNING_THRESHOLD_RATIO)
    if elapsed >= warning_at:
        return SLA_WARNING

    return SLA_OK


def days_until_breach(
    turnover: dict,
    today: date | None = None,
    threshold_days: int = DEFAULT_SLA_THRESHOLD_DAYS,
) -> int | None:
    """Days remaining before SLA breach.  Negative means already breached."""
    move_out = turnover.get("move_out_date")
    if move_out is None:
        return None
    if turnover.get("closed_at") or turnover.get("canceled_at"):
        return None
    today = today or date.today()
    elapsed = (today - move_out).days
    return threshold_days - elapsed


def breach_severity(
    turnover: dict,
    today: date | None = None,
    threshold_days: int = DEFAULT_SLA_THRESHOLD_DAYS,
) -> str:
    """Map SLA risk to a risk_flag severity value."""
    level = sla_risk(turnover, today, threshold_days)
    if level == SLA_BREACH:
        return "CRITICAL"
    if level == SLA_WARNING:
        return "WARNING"
    return "INFO"


def move_in_pressure(turnover: dict, today: date | None = None) -> int | None:
    """Days of buffer between today and move-in.

    Returns None when no move-in date is set.
    Negative means the move-in date has passed without completion.
    """
    move_in = turnover.get("move_in_date")
    if move_in is None:
        return None
    today = today or date.today()
    return (move_in - today).days

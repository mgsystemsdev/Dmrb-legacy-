"""Move-out absence cancellation rule.

Pure function — no database access, no Streamlit imports.

Determines whether a turnover should be auto-cancelled because its unit
has disappeared from the Move Outs report for too many consecutive imports.
"""

from __future__ import annotations


def should_cancel_turnover(missing_moveout_count: int, threshold: int = 2) -> bool:
    """Return ``True`` when the unit has been absent from the Move Outs
    report for *threshold* or more consecutive imports."""
    return missing_moveout_count >= threshold

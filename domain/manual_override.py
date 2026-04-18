"""Manual override resolution rule.

Pure function — no database access, no Streamlit imports.

Centralises the single rule that determines whether an incoming report
value should overwrite the current value when a manual override exists.
"""

from __future__ import annotations

from datetime import datetime


def should_apply_import_value(
    current_value,
    override_timestamp: datetime | None,
    incoming_value,
) -> tuple[bool, bool]:
    """Decide whether to apply an incoming report value.

    Args:
        current_value: The value currently stored in the system.
        override_timestamp: Timestamp of the manual override, or ``None``
            if no override is active.
        incoming_value: The value from the incoming report.

    Returns:
        ``(apply, clear_override)``

        * ``(True, False)``  — no override; accept the report value.
        * ``(True, True)``   — override exists but report now matches;
          accept and clear the override.
        * ``(False, False)`` — override exists and report differs;
          keep the manual value (skip audit should be recorded by caller).
    """
    if override_timestamp is None:
        return (True, False)

    if incoming_value == current_value:
        return (True, True)

    return (False, False)

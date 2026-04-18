"""Write safety guards — DB Writes toggle enforcement and optimistic concurrency."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class WritesDisabledError(Exception):
    pass


class ConcurrencyError(Exception):
    pass


def check_writes_enabled() -> None:
    """Raise WritesDisabledError when the admin DB-writes toggle is off.

    Reads the persistent setting from the database (source of truth). In
    non-Streamlit contexts (tests, CLI) where ``streamlit`` is not
    installed or ``session_state`` does not exist, writes are allowed by
    default so that headless usage is never blocked.
    """
    try:
        from streamlit.runtime.scriptrunner_utils.script_run_context import get_script_run_ctx

        if get_script_run_ctx() is None:
            return

        from services.system_settings_service import get_enable_db_write
    except (ImportError, AttributeError, RuntimeError):
        return

    try:
        enabled = get_enable_db_write()
    except Exception:
        logger.exception("write_guard_check_failed")
        raise WritesDisabledError("Could not verify write permission — writes blocked for safety.")

    if not enabled:
        raise WritesDisabledError(
            "DB writes are disabled. Enable in Admin → DB Writes toggle."
        )


def check_concurrency(entity: dict, table_name: str = "") -> None:
    """Store *updated_at* for later optimistic-concurrency verification.

    Currently a no-op for the JSON backend.  When Postgres is active the
    caller will compare the stored timestamp against the row's current
    ``updated_at`` and raise ``ConcurrencyError`` on mismatch.
    """
    updated_at = entity.get("updated_at")
    if updated_at is not None:
        logger.debug(
            "Concurrency bookmark: %s %s updated_at=%s",
            table_name or "unknown",
            entity.get("id", "?"),
            updated_at,
        )

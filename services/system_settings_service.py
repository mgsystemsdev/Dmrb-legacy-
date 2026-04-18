"""System settings service — DB-backed app settings (e.g. enable DB writes)."""

from __future__ import annotations

import logging

from db.migration_runner import ensure_database_ready
from db.repository import system_settings_repository

logger = logging.getLogger(__name__)

KEY_ENABLE_DB_WRITE = "enable_db_write"


def get_enable_db_write() -> bool:
    """Return True if DB writes are enabled (persistent setting)."""
    try:
        val = system_settings_repository.get_setting(KEY_ENABLE_DB_WRITE)
    except Exception as e:
        # Table may not exist yet; ensure migrations (e.g. 006) are applied and retry once.
        logger.warning("Could not read enable_db_write setting: %s", e)
        try:
            ensure_database_ready()
            val = system_settings_repository.get_setting(KEY_ENABLE_DB_WRITE)
        except Exception:
            return False
    if val is None:
        return False
    return val.lower() in ("true", "1", "yes")


def set_enable_db_write(value: bool) -> None:
    """Persist the enable DB writes setting."""
    system_settings_repository.set_setting(
        KEY_ENABLE_DB_WRITE,
        "true" if value else "false",
    )

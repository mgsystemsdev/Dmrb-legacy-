"""System settings repository — persistent key/value settings."""

from __future__ import annotations

from psycopg2.extras import RealDictCursor

from db.connection import get_connection


def get_setting(key: str) -> str | None:
    """Return the value for key, or None if not found."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT value FROM system_settings WHERE key = %s",
            (key,),
        )
        row = cur.fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    """Insert or update the setting; set updated_at."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO system_settings (key, value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """,
            (key, value),
        )

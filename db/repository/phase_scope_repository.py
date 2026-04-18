"""Phase scope repository — persistent scope configuration per property."""

from __future__ import annotations

from psycopg2.extras import RealDictCursor

from db.connection import get_connection


def get_by_property(property_id: int) -> dict | None:
    """Return the phase_scope row for the property, or None if none exists."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM phase_scope WHERE property_id = %s",
            (property_id,),
        )
        return cur.fetchone()


def get_phase_ids(phase_scope_id: int) -> list[int]:
    """Return list of phase_id for the given phase_scope."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT phase_id FROM phase_scope_phase WHERE phase_scope_id = %s ORDER BY phase_id",
            (phase_scope_id,),
        )
        return [row[0] for row in cur.fetchall()]


def upsert(property_id: int, user_id: int | None = None) -> dict:
    """Insert or update phase_scope for the property; set updated_at. Return the row."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO phase_scope (property_id, user_id, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (property_id) DO UPDATE SET updated_at = NOW()
            RETURNING *
            """,
            (property_id, user_id),
        )
        return cur.fetchone()


def set_phases(phase_scope_id: int, phase_ids: list[int]) -> None:
    """Replace phase_scope_phase rows: delete existing, insert phase_ids."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM phase_scope_phase WHERE phase_scope_id = %s",
            (phase_scope_id,),
        )
        for phase_id in phase_ids:
            cur.execute(
                "INSERT INTO phase_scope_phase (phase_scope_id, phase_id) VALUES (%s, %s)",
                (phase_scope_id, phase_id),
            )

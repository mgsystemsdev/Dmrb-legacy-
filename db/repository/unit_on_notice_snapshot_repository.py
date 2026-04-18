"""Repository for unit_on_notice_snapshot — On Notice units with no turnover, for midnight automation."""

from __future__ import annotations

from datetime import date

from psycopg2.extras import RealDictCursor

from db.connection import get_connection


def upsert(
    property_id: int,
    unit_id: int,
    available_date: date,
    move_in_ready_date: date | None = None,
) -> None:
    """Insert or update snapshot row for (property_id, unit_id). Latest import wins."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO unit_on_notice_snapshot
                (property_id, unit_id, available_date, move_in_ready_date)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (property_id, unit_id)
            DO UPDATE SET
                available_date = EXCLUDED.available_date,
                move_in_ready_date = EXCLUDED.move_in_ready_date,
                updated_at = NOW()
            """,
            (property_id, unit_id, available_date, move_in_ready_date),
        )


def get_eligible_for_automation(property_id: int, today: date) -> list[dict]:
    """Rows where available_date <= today. Caller must verify no open turnover per unit."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT property_id, unit_id, available_date, move_in_ready_date
            FROM unit_on_notice_snapshot
            WHERE property_id = %s AND available_date <= %s
            ORDER BY available_date
            """,
            (property_id, today),
        )
        return cur.fetchall()


def delete_by_unit(property_id: int, unit_id: int) -> None:
    """Remove snapshot for a unit (e.g. after turnover created)."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM unit_on_notice_snapshot
            WHERE property_id = %s AND unit_id = %s
            """,
            (property_id, unit_id),
        )

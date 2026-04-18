"""lifecycle_event — append-only rows; property_id on every query.

There is no UPDATE/DELETE path here; the table uses ``prevent_mutation``.
"""

from __future__ import annotations

from datetime import datetime

from psycopg2.extras import Json, RealDictCursor

from db.connection import get_connection


def insert(
    property_id: int,
    turnover_id: int,
    to_phase: str,
    actor: str,
    source: str,
    *,
    from_phase: str | None = None,
    event_type: str = "PHASE_TRANSITION",
    payload: dict | None = None,
    occurred_at: datetime | None = None,
) -> dict:
    """Insert one lifecycle event. ``occurred_at`` defaults to DB ``NOW()`` when omitted."""
    payload_adapt = Json(payload) if payload is not None else None
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        if occurred_at is None:
            cur.execute(
                """
                INSERT INTO lifecycle_event (
                    property_id, turnover_id, from_phase, to_phase,
                    event_type, actor, source, payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    property_id,
                    turnover_id,
                    from_phase,
                    to_phase,
                    event_type,
                    actor,
                    source,
                    payload_adapt,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO lifecycle_event (
                    property_id, turnover_id, from_phase, to_phase,
                    event_type, actor, source, payload, occurred_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    property_id,
                    turnover_id,
                    from_phase,
                    to_phase,
                    event_type,
                    actor,
                    source,
                    payload_adapt,
                    occurred_at,
                ),
            )
        return cur.fetchone()


def get_by_id(property_id: int, lifecycle_event_id: int) -> dict | None:
    """Single row scoped to ``property_id``."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM lifecycle_event
            WHERE property_id = %s AND lifecycle_event_id = %s
            """,
            (property_id, lifecycle_event_id),
        )
        return cur.fetchone()


def list_for_turnover(
    property_id: int,
    turnover_id: int,
    *,
    limit: int = 500,
    oldest_first: bool = True,
) -> list[dict]:
    """Events for one turnover, property-scoped. Default order: timeline (oldest → newest)."""
    if oldest_first:
        sql = """
            SELECT * FROM lifecycle_event
            WHERE property_id = %s AND turnover_id = %s
            ORDER BY occurred_at ASC, lifecycle_event_id ASC
            LIMIT %s
            """
    else:
        sql = """
            SELECT * FROM lifecycle_event
            WHERE property_id = %s AND turnover_id = %s
            ORDER BY occurred_at DESC, lifecycle_event_id DESC
            LIMIT %s
            """
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (property_id, turnover_id, limit))
        return cur.fetchall()


def list_for_property(
    property_id: int,
    *,
    limit: int = 500,
    newest_first: bool = True,
) -> list[dict]:
    """Recent events across turnovers for one property (admin / diagnostics)."""
    if newest_first:
        sql = """
            SELECT * FROM lifecycle_event
            WHERE property_id = %s
            ORDER BY occurred_at DESC, lifecycle_event_id DESC
            LIMIT %s
            """
    else:
        sql = """
            SELECT * FROM lifecycle_event
            WHERE property_id = %s
            ORDER BY occurred_at ASC, lifecycle_event_id ASC
            LIMIT %s
            """
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (property_id, limit))
        return cur.fetchall()

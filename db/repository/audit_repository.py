from __future__ import annotations

from psycopg2.extras import RealDictCursor

from db.connection import get_connection


def insert(
    property_id: int,
    entity_type: str,
    entity_id: int,
    field_name: str,
    old_value: str | None,
    new_value: str | None,
    actor: str,
    source: str,
) -> dict:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO audit_log (
                property_id, entity_type, entity_id, field_name,
                old_value, new_value, actor, source
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                property_id,
                entity_type,
                entity_id,
                field_name,
                old_value,
                new_value,
                actor,
                source,
            ),
        )
        return cur.fetchone()


def get_by_entity(
    entity_type: str,
    entity_id: int,
    limit: int = 100,
) -> list[dict]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM audit_log
            WHERE entity_type = %s AND entity_id = %s
            ORDER BY changed_at DESC
            LIMIT %s
            """,
            (entity_type, entity_id, limit),
        )
        return cur.fetchall()


def get_by_property(property_id: int, limit: int = 200) -> list[dict]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM audit_log
            WHERE property_id = %s
            ORDER BY changed_at DESC
            LIMIT %s
            """,
            (property_id, limit),
        )
        return cur.fetchall()

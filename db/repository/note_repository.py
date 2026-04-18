from __future__ import annotations

from psycopg2.extras import RealDictCursor

from db.connection import get_connection


def get_by_turnover_ids(turnover_ids: list[int]) -> dict[int, list]:
    if not turnover_ids:
        return {}
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM note
            WHERE turnover_id = ANY(%s) AND resolved_at IS NULL
            ORDER BY created_at DESC
            """,
            (turnover_ids,),
        )
        rows = cur.fetchall()
    result: dict[int, list] = {tid: [] for tid in turnover_ids}
    for row in rows:
        result[row["turnover_id"]].append(row)
    return result


def get_by_turnover(turnover_id: int, include_resolved: bool = False) -> list[dict]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        if include_resolved:
            cur.execute(
                "SELECT * FROM note WHERE turnover_id = %s ORDER BY created_at DESC",
                (turnover_id,),
            )
        else:
            cur.execute(
                """
                SELECT * FROM note
                WHERE turnover_id = %s AND resolved_at IS NULL
                ORDER BY created_at DESC
                """,
                (turnover_id,),
            )
        return cur.fetchall()


def get_by_id(note_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM note WHERE note_id = %s", (note_id,))
        return cur.fetchone()


def insert(property_id: int, turnover_id: int, severity: str, text: str) -> dict:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO note (property_id, turnover_id, severity, text)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (property_id, turnover_id, severity, text),
        )
        return cur.fetchone()


def resolve(note_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE note SET resolved_at = NOW()
            WHERE note_id = %s AND resolved_at IS NULL
            RETURNING *
            """,
            (note_id,),
        )
        return cur.fetchone()

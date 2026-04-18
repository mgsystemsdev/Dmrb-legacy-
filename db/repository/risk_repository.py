from __future__ import annotations

from psycopg2.extras import RealDictCursor

from db.connection import get_connection


def get_open_by_turnover(turnover_id: int) -> list[dict]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM risk_flag
            WHERE turnover_id = %s AND resolved_at IS NULL
            ORDER BY opened_at
            """,
            (turnover_id,),
        )
        return cur.fetchall()


def get_open_by_turnover_ids(turnover_ids: list[int]) -> dict[int, list]:
    if not turnover_ids:
        return {}
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM risk_flag
            WHERE turnover_id = ANY(%s) AND resolved_at IS NULL
            ORDER BY opened_at
            """,
            (turnover_ids,),
        )
        rows = cur.fetchall()
    result: dict[int, list] = {tid: [] for tid in turnover_ids}
    for row in rows:
        result[row["turnover_id"]].append(row)
    return result


def get_by_turnover(turnover_id: int) -> list[dict]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM risk_flag WHERE turnover_id = %s ORDER BY opened_at",
            (turnover_id,),
        )
        return cur.fetchall()


def get_by_id(risk_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM risk_flag WHERE risk_id = %s", (risk_id,))
        return cur.fetchone()


def upsert_open(
    property_id: int,
    turnover_id: int,
    risk_type: str,
    severity: str,
) -> dict:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM risk_flag
            WHERE turnover_id = %s AND risk_type = %s AND resolved_at IS NULL
            """,
            (turnover_id, risk_type),
        )
        existing = cur.fetchone()
        if existing:
            if existing["severity"] != severity:
                cur.execute(
                    """
                    UPDATE risk_flag SET severity = %s
                    WHERE risk_id = %s RETURNING *
                    """,
                    (severity, existing["risk_id"]),
                )
                return cur.fetchone()
            return existing
        cur.execute(
            """
            INSERT INTO risk_flag (property_id, turnover_id, risk_type, severity)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (property_id, turnover_id, risk_type, severity),
        )
        return cur.fetchone()


def resolve(risk_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE risk_flag SET resolved_at = NOW()
            WHERE risk_id = %s AND resolved_at IS NULL
            RETURNING *
            """,
            (risk_id,),
        )
        return cur.fetchone()


def resolve_by_type(turnover_id: int, risk_type: str) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE risk_flag SET resolved_at = NOW()
            WHERE turnover_id = %s AND risk_type = %s AND resolved_at IS NULL
            RETURNING *
            """,
            (turnover_id, risk_type),
        )
        return cur.fetchone()


# ── SLA Events ───────────────────────────────────────────────────────────────

def get_open_sla_breach(turnover_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM sla_event
            WHERE turnover_id = %s AND breach_resolved_at IS NULL
            """,
            (turnover_id,),
        )
        return cur.fetchone()


def insert_sla_event(
    property_id: int,
    turnover_id: int,
    threshold_days: int,
) -> dict:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO sla_event (
                property_id, turnover_id, breach_started_at, threshold_days
            )
            VALUES (%s, %s, NOW(), %s)
            RETURNING *
            """,
            (property_id, turnover_id, threshold_days),
        )
        return cur.fetchone()


def resolve_sla_event(sla_event_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE sla_event SET breach_resolved_at = NOW()
            WHERE sla_event_id = %s AND breach_resolved_at IS NULL
            RETURNING *
            """,
            (sla_event_id,),
        )
        return cur.fetchone()

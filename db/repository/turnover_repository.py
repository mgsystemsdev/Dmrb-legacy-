from __future__ import annotations

from datetime import date

from psycopg2.extras import RealDictCursor

from db.connection import get_connection


def get_open_by_property(
    property_id: int,
    phase_ids: list[int] | None = None,
) -> list[dict]:
    """Open turnovers for the property. If phase_ids is set, only units in those phases."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        if phase_ids is not None:
            cur.execute(
                """
                SELECT t.* FROM turnover t
                JOIN unit u ON u.unit_id = t.unit_id AND u.property_id = t.property_id
                WHERE t.property_id = %s
                  AND t.closed_at IS NULL
                  AND t.canceled_at IS NULL
                  AND u.phase_id = ANY(%s)
                ORDER BY t.move_out_date
                """,
                (property_id, phase_ids),
            )
        else:
            cur.execute(
                """
                SELECT * FROM turnover
                WHERE property_id = %s
                  AND closed_at IS NULL
                  AND canceled_at IS NULL
                ORDER BY move_out_date
                """,
                (property_id,),
            )
        return cur.fetchall()


def count_open_turnovers(property_id: int) -> int:
    """Count open (not closed, not canceled) turnovers for the property."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)::bigint FROM turnover
            WHERE property_id = %s
              AND closed_at IS NULL
              AND canceled_at IS NULL
            """,
            (property_id,),
        )
        row = cur.fetchone()
    return int(row[0]) if row else 0


def get_by_id(turnover_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM turnover WHERE turnover_id = %s",
            (turnover_id,),
        )
        return cur.fetchone()


def get_open_by_unit(unit_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM turnover
            WHERE unit_id = %s
              AND closed_at IS NULL
              AND canceled_at IS NULL
            """,
            (unit_id,),
        )
        return cur.fetchone()


def insert(
    property_id: int,
    unit_id: int,
    move_out_date: date,
    *,
    move_in_date: date | None = None,
    scheduled_move_out_date: date | None = None,
) -> dict:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO turnover (
                property_id, unit_id, move_out_date,
                move_in_date, scheduled_move_out_date
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (property_id, unit_id, move_out_date, move_in_date, scheduled_move_out_date),
        )
        return cur.fetchone()


_TURNOVER_UPDATABLE = frozenset({
    "move_out_date", "move_in_date", "report_ready_date", "available_date",
    "availability_status", "scheduled_move_out_date", "confirmed_move_out_date",
    "legal_confirmation_source", "legal_confirmed_at",
    "manual_ready_status", "manual_ready_confirmed_at",
    "closed_at", "canceled_at", "cancel_reason",
    "missing_moveout_count", "move_out_manual_override_at",
    "move_in_manual_override_at",
    "ready_manual_override_at", "status_manual_override_at",
    "wd_notified_at", "wd_installed_at",
})


def update(turnover_id: int, **fields) -> dict | None:
    if not fields:
        return get_by_id(turnover_id)
    # Only columns in _TURNOVER_UPDATABLE are ever interpolated into the query.
    # Values are always passed as %s parameters — never interpolated.
    safe_fields = {k: v for k, v in fields.items() if k in _TURNOVER_UPDATABLE}
    if not safe_fields:
        return get_by_id(turnover_id)
    set_clause = ", ".join(f"{col} = %s" for col in safe_fields)
    values = list(safe_fields.values()) + [turnover_id]
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"UPDATE turnover SET {set_clause} WHERE turnover_id = %s RETURNING *",
            values,
        )
        return cur.fetchone()


def get_overrides(property_id: int, turnover_id: int) -> list[dict]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM turnover_task_override
            WHERE property_id = %s AND turnover_id = %s
            """,
            (property_id, turnover_id),
        )
        return cur.fetchall()


def upsert_override(
    property_id: int,
    turnover_id: int,
    task_type: str,
    *,
    required_override: bool | None = None,
    blocking_override: bool | None = None,
) -> dict:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO turnover_task_override (
                property_id, turnover_id, task_type,
                required_override, blocking_override
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (property_id, turnover_id, task_type)
            DO UPDATE SET
                required_override = EXCLUDED.required_override,
                blocking_override = EXCLUDED.blocking_override
            RETURNING *
            """,
            (property_id, turnover_id, task_type, required_override, blocking_override),
        )
        return cur.fetchone()

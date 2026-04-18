from __future__ import annotations

from datetime import date

from psycopg2.extras import RealDictCursor

from db.connection import get_connection


# ── Task Templates ───────────────────────────────────────────────────────────

def get_templates_by_phase(phase_id: int, active_only: bool = True) -> list[dict]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        if active_only:
            cur.execute(
                """
                SELECT * FROM task_template
                WHERE phase_id = %s AND is_active = TRUE
                ORDER BY sort_order
                """,
                (phase_id,),
            )
        else:
            cur.execute(
                "SELECT * FROM task_template WHERE phase_id = %s ORDER BY sort_order",
                (phase_id,),
            )
        return cur.fetchall()


def insert_template(
    property_id: int,
    phase_id: int,
    task_type: str,
    offset_days_from_move_out: int,
    *,
    sort_order: int = 0,
    required: bool = True,
    blocking: bool = True,
) -> dict:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO task_template (
                property_id, phase_id, task_type, offset_days_from_move_out,
                sort_order, required, blocking
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                property_id, phase_id, task_type, offset_days_from_move_out,
                sort_order, required, blocking,
            ),
        )
        return cur.fetchone()


def insert_template_if_no_active_for_phase(
    property_id: int,
    phase_id: int,
    task_type: str,
    offset_days_from_move_out: int,
    *,
    sort_order: int = 0,
    required: bool = True,
    blocking: bool = True,
) -> dict | None:
    """Insert one template when no *active* row exists for (phase_id, task_type).

    Matches migration 007_seed_task_templates.sql NOT EXISTS semantics.
    Returns the new row, or None if an active template already exists.
    """
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO task_template (
                property_id, phase_id, task_type, offset_days_from_move_out,
                sort_order, required, blocking, is_active
            )
            SELECT %s, %s, %s, %s, %s, %s, %s, TRUE
            WHERE NOT EXISTS (
                SELECT 1 FROM task_template t
                WHERE t.phase_id = %s
                  AND t.task_type = %s
                  AND t.is_active = TRUE
            )
            RETURNING *
            """,
            (
                property_id,
                phase_id,
                task_type,
                offset_days_from_move_out,
                sort_order,
                required,
                blocking,
                phase_id,
                task_type,
            ),
        )
        return cur.fetchone()


def update_template(
    template_id: int,
    *,
    task_type: str | None = None,
    sort_order: int | None = None,
    offset_days_from_move_out: int | None = None,
    required: bool | None = None,
    blocking: bool | None = None,
    is_active: bool | None = None,
) -> dict | None:
    fields = {
        "task_type": task_type,
        "sort_order": sort_order,
        "offset_days_from_move_out": offset_days_from_move_out,
        "required": required,
        "blocking": blocking,
        "is_active": is_active,
    }
    # Drop fields that were not supplied (None means "caller did not pass this").
    safe_fields = {k: v for k, v in fields.items() if v is not None}
    if not safe_fields:
        return _get_template_by_id(template_id)
    # Column names come from the literal dict above — never from caller input.
    # Values are passed as %s parameters.
    set_clause = ", ".join(f"{col} = %s" for col in safe_fields)
    values = list(safe_fields.values()) + [template_id]
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"UPDATE task_template SET {set_clause} WHERE template_id = %s RETURNING *",
            values,
        )
        return cur.fetchone()


def _get_template_by_id(template_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM task_template WHERE template_id = %s",
            (template_id,),
        )
        return cur.fetchone()


# ── Tasks ────────────────────────────────────────────────────────────────────

def get_by_turnover(turnover_id: int) -> list[dict]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM task WHERE turnover_id = %s ORDER BY task_type",
            (turnover_id,),
        )
        return cur.fetchall()


def get_by_turnover_ids(turnover_ids: list[int]) -> dict[int, list]:
    if not turnover_ids:
        return {}
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM task WHERE turnover_id = ANY(%s) ORDER BY task_type",
            (turnover_ids,),
        )
        rows = cur.fetchall()
    result: dict[int, list] = {tid: [] for tid in turnover_ids}
    for row in rows:
        result[row["turnover_id"]].append(row)
    return result


def get_completed_on(
    property_id: int,
    completed_date: date,
    phase_ids: list[int] | None = None,
) -> list[dict]:
    """Completed tasks on ``completed_date`` with unit code; optional unit phase filter."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        base = """
            SELECT
                t.task_id,
                t.task_type,
                t.assignee,
                u.unit_code_norm AS unit_code
            FROM task t
            INNER JOIN turnover tr
                ON tr.turnover_id = t.turnover_id
                AND tr.property_id = t.property_id
            INNER JOIN unit u
                ON u.unit_id = tr.unit_id
                AND u.property_id = tr.property_id
            WHERE t.property_id = %s
              AND t.execution_status = 'COMPLETED'
              AND t.completed_date = %s
        """
        if phase_ids is not None:
            cur.execute(
                base
                + " AND u.phase_id = ANY(%s) ORDER BY u.unit_code_norm, t.task_type",
                (property_id, completed_date, phase_ids),
            )
        else:
            cur.execute(
                base + " ORDER BY u.unit_code_norm, t.task_type",
                (property_id, completed_date),
            )
        return cur.fetchall()


def get_by_id(task_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM task WHERE task_id = %s", (task_id,))
        return cur.fetchone()


def insert(
    property_id: int,
    turnover_id: int,
    task_type: str,
    *,
    scheduled_date: date | None = None,
    vendor_due_date: date | None = None,
    required: bool = True,
    blocking: bool = True,
    assignee: str | None = None,
) -> dict:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO task (
                property_id, turnover_id, task_type,
                scheduled_date, vendor_due_date,
                required, blocking, assignee
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                property_id, turnover_id, task_type,
                scheduled_date, vendor_due_date,
                required, blocking, assignee,
            ),
        )
        return cur.fetchone()


_TASK_UPDATABLE = frozenset({
    "scheduled_date", "vendor_due_date", "execution_status",
    "vendor_completed_at", "completed_date",
    "required", "blocking", "assignee",
})


def update(task_id: int, **fields) -> dict | None:
    if not fields:
        return get_by_id(task_id)
    # Only columns in _TASK_UPDATABLE are ever interpolated into the query.
    # Values are always passed as %s parameters — never interpolated.
    safe_fields = {k: v for k, v in fields.items() if k in _TASK_UPDATABLE}
    if not safe_fields:
        return get_by_id(task_id)
    set_clause = ", ".join(f"{col} = %s" for col in safe_fields)
    values = list(safe_fields.values()) + [task_id]
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"UPDATE task SET {set_clause} WHERE task_id = %s RETURNING *",
            values,
        )
        return cur.fetchone()

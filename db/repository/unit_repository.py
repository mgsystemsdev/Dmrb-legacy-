from __future__ import annotations

from psycopg2.extras import RealDictCursor

from db.connection import get_connection


def get_by_property(
    property_id: int,
    active_only: bool = True,
    phase_ids: list[int] | None = None,
) -> list[dict]:
    """Units for the property. If phase_ids is set, only units in those phases."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        base = "SELECT * FROM unit WHERE property_id = %s"
        params: list = [property_id]
        if active_only:
            base += " AND is_active = TRUE"
        if phase_ids is not None:
            base += " AND phase_id = ANY(%s)"
            params.append(phase_ids)
        base += " ORDER BY unit_code_norm"
        cur.execute(base, params)
        return cur.fetchall()


def get_by_id(unit_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM unit WHERE unit_id = %s", (unit_id,))
        return cur.fetchone()


def get_by_identity_key(property_id: int, unit_identity_key: str) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM unit
            WHERE property_id = %s AND unit_identity_key = %s
            """,
            (property_id, unit_identity_key),
        )
        return cur.fetchone()


def get_by_code_norm(property_id: int, unit_code_norm: str) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM unit
            WHERE property_id = %s AND unit_code_norm = %s
            """,
            (property_id, unit_code_norm),
        )
        return cur.fetchone()


def insert(
    property_id: int,
    unit_code_raw: str,
    unit_code_norm: str,
    unit_identity_key: str,
    *,
    phase_id: int | None = None,
    building_id: int | None = None,
    floor_plan: str | None = None,
    gross_sq_ft: int | None = None,
    has_carpet: bool = False,
    has_wd_expected: bool = False,
) -> dict:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO unit (
                property_id, unit_code_raw, unit_code_norm, unit_identity_key,
                phase_id, building_id, floor_plan, gross_sq_ft,
                has_carpet, has_wd_expected
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                property_id, unit_code_raw, unit_code_norm, unit_identity_key,
                phase_id, building_id, floor_plan, gross_sq_ft,
                has_carpet, has_wd_expected,
            ),
        )
        return cur.fetchone()


def list_unit_master_import_units(property_id: int) -> list[dict]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                unit_code_raw,
                floor_plan  AS unit_type,
                gross_sq_ft AS square_feet
            FROM unit
            WHERE property_id = %s
            ORDER BY unit_code_raw
            """,
            (property_id,),
        )
        return cur.fetchall()


def update(unit_id: int, **fields) -> dict | None:
    if not fields:
        return get_by_id(unit_id)
    allowed = {
        "unit_code_raw", "unit_code_norm", "unit_identity_key",
        "phase_id", "building_id", "floor_plan", "gross_sq_ft",
        "has_carpet", "has_wd_expected", "is_active",
    }
    filtered = {k: v for k, v in fields.items() if k in allowed}
    if not filtered:
        return get_by_id(unit_id)
    set_clause = ", ".join(f"{col} = %s" for col in filtered)
    values = list(filtered.values()) + [unit_id]
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"UPDATE unit SET {set_clause} WHERE unit_id = %s RETURNING *",
            values,
        )
        return cur.fetchone()

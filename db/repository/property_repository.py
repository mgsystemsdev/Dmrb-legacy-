from __future__ import annotations

from psycopg2.extras import RealDictCursor

from db.connection import get_connection


def get_all() -> list[dict]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM property ORDER BY name")
        return cur.fetchall()


def get_by_id(property_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM property WHERE property_id = %s", (property_id,))
        return cur.fetchone()


def insert(name: str) -> dict:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO property (name) VALUES (%s) RETURNING *",
            (name,),
        )
        return cur.fetchone()


def update(property_id: int, name: str) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "UPDATE property SET name = %s WHERE property_id = %s RETURNING *",
            (name, property_id),
        )
        return cur.fetchone()


def get_phases(property_id: int) -> list[dict]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM phase WHERE property_id = %s ORDER BY phase_code",
            (property_id,),
        )
        return cur.fetchall()


def get_phase_by_id(phase_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM phase WHERE phase_id = %s", (phase_id,))
        return cur.fetchone()


def insert_phase(property_id: int, phase_code: str, name: str | None = None) -> dict:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO phase (property_id, phase_code, name)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (property_id, phase_code, name),
        )
        return cur.fetchone()


def get_buildings(phase_id: int) -> list[dict]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM building WHERE phase_id = %s ORDER BY building_code",
            (phase_id,),
        )
        return cur.fetchall()


def get_building_by_id(building_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM building WHERE building_id = %s", (building_id,))
        return cur.fetchone()


def insert_building(
    property_id: int,
    phase_id: int,
    building_code: str,
    name: str | None = None,
) -> dict:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO building (property_id, phase_id, building_code, name)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (property_id, phase_id, building_code, name),
        )
        return cur.fetchone()

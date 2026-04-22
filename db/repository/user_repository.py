from __future__ import annotations

from psycopg2.extras import RealDictCursor

from db.connection import get_connection


def normalize_username(username: str) -> str:
    return username.strip().lower()


def count_all() -> int:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM app_user")
        return int(cur.fetchone()[0])


# Distinct key for first-admin bootstrap (serialized with pg_advisory_xact_lock).
_BOOTSTRAP_ADVISORY_KEY = 584_291_738


def acquire_bootstrap_advisory_lock() -> None:
    """Hold for the rest of the current transaction; serializes bootstrap vs other writers."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (_BOOTSTRAP_ADVISORY_KEY,))


def get_active_by_username(username: str) -> dict | None:
    key = normalize_username(username)
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT user_id, username, password_hash, role, is_active
            FROM app_user
            WHERE username = %s AND is_active = TRUE
            """,
            (key,),
        )
        return cur.fetchone()


def list_all_for_admin() -> list[dict]:
    """All users for admin UI (no password_hash)."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT user_id, username, role, is_active, created_at, updated_at
            FROM app_user
            ORDER BY username
            """
        )
        return cur.fetchall()


def get_by_id(user_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT user_id, username, password_hash, role, is_active, created_at, updated_at
            FROM app_user
            WHERE user_id = %s
            """,
            (user_id,),
        )
        return cur.fetchone()


def insert(username: str, password_hash: str, role: str) -> dict:
    key = normalize_username(username)
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO app_user (username, password_hash, role)
            VALUES (%s, %s, %s)
            RETURNING user_id, username, role, is_active, created_at, updated_at
            """,
            (key, password_hash, role),
        )
        return cur.fetchone()


def update_password_hash(user_id: int, password_hash: str) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE app_user
            SET password_hash = %s
            WHERE user_id = %s
            RETURNING user_id, username, role, is_active, created_at, updated_at
            """,
            (password_hash, user_id),
        )
        return cur.fetchone()


def update_role(user_id: int, role: str) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE app_user
            SET role = %s
            WHERE user_id = %s
            RETURNING user_id, username, role, is_active, created_at, updated_at
            """,
            (role, user_id),
        )
        return cur.fetchone()


def set_active(user_id: int, is_active: bool) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE app_user
            SET is_active = %s
            WHERE user_id = %s
            RETURNING user_id, username, role, is_active, created_at, updated_at
            """,
            (is_active, user_id),
        )
        return cur.fetchone()

from __future__ import annotations

import json

from psycopg2.extras import RealDictCursor, Json

from db.connection import get_connection


# ── Batches ──────────────────────────────────────────────────────────────────

def get_batches_by_property(property_id: int, limit: int = 50) -> list[dict]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM import_batch
            WHERE property_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (property_id, limit),
        )
        return cur.fetchall()


def get_batch_by_id(batch_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM import_batch WHERE batch_id = %s",
            (batch_id,),
        )
        return cur.fetchone()


def get_batch_by_checksum(property_id: int, checksum: str, report_type: str) -> dict | None:
    """Return the latest batch for (property_id, checksum, report_type), or None."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM import_batch
            WHERE property_id = %s AND checksum = %s AND report_type = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (property_id, checksum, report_type),
        )
        return cur.fetchone()


def insert_batch(
    property_id: int,
    report_type: str,
    checksum: str,
    status: str,
    record_count: int = 0,
) -> dict:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO import_batch (
                property_id, report_type, checksum, status, record_count
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (property_id, report_type, checksum, status, record_count),
        )
        return cur.fetchone()


def update_batch_status(batch_id: int, status: str, record_count: int | None = None) -> dict | None:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        if record_count is not None:
            cur.execute(
                """
                UPDATE import_batch
                SET status = %s, record_count = %s
                WHERE batch_id = %s
                RETURNING *
                """,
                (status, record_count, batch_id),
            )
        else:
            cur.execute(
                """
                UPDATE import_batch SET status = %s
                WHERE batch_id = %s
                RETURNING *
                """,
                (status, batch_id),
            )
        return cur.fetchone()


# ── Diagnostics ──────────────────────────────────────────────────────────────

def get_import_batches(property_id: int, limit: int = 50) -> list[dict]:
    """Return recent batches with per-status row counts for diagnostics."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                ib.batch_id,
                ib.report_type,
                ib.status,
                ib.record_count,
                ib.created_at,
                COUNT(ir.row_id) FILTER (
                    WHERE ir.validation_status = 'OK'
                )   AS applied_count,
                COUNT(ir.row_id) FILTER (
                    WHERE ir.validation_status IN ('CONFLICT', 'SKIPPED_OVERRIDE', 'IGNORED')
                )   AS conflict_count,
                COUNT(ir.row_id) FILTER (
                    WHERE ir.validation_status = 'INVALID'
                )   AS invalid_count
            FROM import_batch ib
            LEFT JOIN import_row ir ON ir.batch_id = ib.batch_id
            WHERE ib.property_id = %s
            GROUP BY ib.batch_id
            ORDER BY ib.created_at DESC
            LIMIT %s
            """,
            (property_id, limit),
        )
        return cur.fetchall()


def get_import_rows(batch_id: int) -> list[dict]:
    """Return row-level results for a single batch (diagnostics drill-down)."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                row_id,
                unit_code_norm  AS unit,
                validation_status,
                conflict_reason,
                move_out_date,
                move_in_date,
                raw_json
            FROM import_row
            WHERE batch_id = %s
            ORDER BY row_id
            """,
            (batch_id,),
        )
        return cur.fetchall()


# ── Rows ─────────────────────────────────────────────────────────────────────

def get_rows_by_batch(batch_id: int) -> list[dict]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM import_row WHERE batch_id = %s ORDER BY row_id",
            (batch_id,),
        )
        return cur.fetchall()


def insert_row(
    property_id: int,
    batch_id: int,
    validation_status: str,
    raw_json: dict,
    *,
    unit_code_raw: str | None = None,
    unit_code_norm: str | None = None,
    move_out_date=None,
    move_in_date=None,
    conflict_flag: bool = False,
    conflict_reason: str | None = None,
) -> dict:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO import_row (
                property_id, batch_id, validation_status, raw_json,
                unit_code_raw, unit_code_norm,
                move_out_date, move_in_date,
                conflict_flag, conflict_reason
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                property_id, batch_id, validation_status, Json(raw_json),
                unit_code_raw, unit_code_norm,
                move_out_date, move_in_date,
                conflict_flag, conflict_reason,
            ),
        )
        return cur.fetchone()


def get_rows_by_property(property_id: int) -> list[dict]:
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM import_row WHERE property_id = %s ORDER BY row_id",
            (property_id,),
        )
        return cur.fetchall()


def get_missing_move_out_rows(
    property_id: int,
    phase_ids: list[int] | None = None,
) -> list[dict]:
    """Return unresolved CONFLICT rows with reason MOVE_IN_WITHOUT_OPEN_TURNOVER.

    When phase_ids is set, only rows for units in those phases are returned.
    """
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        if phase_ids is not None:
            cur.execute(
                """
                SELECT ir.*, ib.report_type, ib.created_at AS batch_created_at, u.unit_id
                FROM import_row ir
                JOIN import_batch ib ON ib.batch_id = ir.batch_id
                JOIN unit u ON u.property_id = ir.property_id AND u.unit_code_norm = ir.unit_code_norm
                WHERE ir.property_id = %s
                  AND ir.validation_status = 'CONFLICT'
                  AND ir.conflict_reason = 'MOVE_IN_WITHOUT_OPEN_TURNOVER'
                  AND ir.resolved_at IS NULL
                  AND u.phase_id = ANY(%s)
                ORDER BY ir.created_at DESC
                """,
                (property_id, phase_ids),
            )
        else:
            cur.execute(
                """
                SELECT ir.*, ib.report_type, ib.created_at AS batch_created_at, u.unit_id
                FROM import_row ir
                JOIN import_batch ib ON ib.batch_id = ir.batch_id
                JOIN unit u ON u.property_id = ir.property_id AND u.unit_code_norm = ir.unit_code_norm
                WHERE ir.property_id = %s
                  AND ir.validation_status = 'CONFLICT'
                  AND ir.conflict_reason = 'MOVE_IN_WITHOUT_OPEN_TURNOVER'
                  AND ir.resolved_at IS NULL
                ORDER BY ir.created_at DESC
                """,
                (property_id,),
            )
        return cur.fetchall()


def get_override_conflicts(property_id: int) -> list[dict]:
    """Return unresolved override-conflict rows with audit-level field detail.

    Matches rows where the import pipeline skipped a field due to a manual
    override (SKIPPED_OVERRIDE) or partially skipped fields while applying
    others (OK + PARTIAL_OVERRIDE_SKIP).

    For each such row, the audit_log entries with source ending in
    ':override_skip' provide the field name and the report value that was
    rejected.  The current manual value is read from the turnover row.
    """
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                ir.row_id,
                ir.batch_id,
                ir.unit_code_norm,
                ir.validation_status,
                ir.conflict_reason,
                ir.raw_json,
                ir.created_at   AS detected_at,
                ib.report_type,
                al.field_name   AS conflict_field,
                al.new_value    AS report_value,
                al.entity_id    AS turnover_id
            FROM import_row ir
            JOIN import_batch ib ON ib.batch_id = ir.batch_id
            JOIN audit_log al
              ON al.entity_type = 'turnover'
             AND al.source LIKE '%%:override_skip'
             AND al.changed_at BETWEEN ir.created_at - INTERVAL '5 seconds'
                                    AND ir.created_at + INTERVAL '5 seconds'
             AND al.property_id = ir.property_id
            WHERE ir.property_id = %s
              AND (
                  ir.validation_status = 'SKIPPED_OVERRIDE'
                  OR (ir.validation_status = 'OK'
                      AND ir.conflict_reason = 'PARTIAL_OVERRIDE_SKIP')
              )
              AND ir.resolved_at IS NULL
            ORDER BY ir.created_at DESC
            """,
            (property_id,),
        )
        return cur.fetchall()


def get_invalid_import_rows(property_id: int) -> list[dict]:
    """Return unresolved INVALID import rows for the Invalid Data queue."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                ir.row_id,
                ir.unit_code_norm   AS unit,
                ir.batch_id,
                ir.conflict_reason,
                ir.move_out_date,
                ir.move_in_date,
                ir.raw_json,
                ir.created_at       AS detected_at,
                ib.report_type
            FROM import_row ir
            JOIN import_batch ib ON ib.batch_id = ir.batch_id
            WHERE ir.property_id = %s
              AND ir.validation_status = 'INVALID'
              AND ir.resolved_at IS NULL
            ORDER BY ir.created_at DESC
            """,
            (property_id,),
        )
        return cur.fetchall()


def get_fas_rows(
    property_id: int,
    phase_ids: list[int] | None = None,
) -> list[dict]:
    """Return PENDING_FAS import rows with note_text extracted from raw_json.

    When phase_ids is set, only rows for units in those phases are returned.
    """
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        if phase_ids is not None:
            cur.execute(
                """
                SELECT
                    ir.row_id,
                    ir.unit_code_norm,
                    ir.raw_json,
                    ir.raw_json->>'fas_date'     AS fas_date,
                    ir.raw_json->>'note_text'    AS note_text,
                    ir.created_at                AS imported_at,
                    ib.report_type
                FROM import_row ir
                JOIN import_batch ib ON ib.batch_id = ir.batch_id
                JOIN unit u ON u.property_id = ir.property_id AND u.unit_code_norm = ir.unit_code_norm
                WHERE ir.property_id = %s
                  AND ib.report_type = 'PENDING_FAS'
                  AND u.phase_id = ANY(%s)
                ORDER BY ir.created_at DESC
                """,
                (property_id, phase_ids),
            )
        else:
            cur.execute(
                """
                SELECT
                    ir.row_id,
                    ir.unit_code_norm,
                    ir.raw_json,
                    ir.raw_json->>'fas_date'     AS fas_date,
                    ir.raw_json->>'note_text'    AS note_text,
                    ir.created_at                AS imported_at,
                    ib.report_type
                FROM import_row ir
                JOIN import_batch ib ON ib.batch_id = ir.batch_id
                WHERE ir.property_id = %s
                  AND ib.report_type = 'PENDING_FAS'
                ORDER BY ir.created_at DESC
                """,
                (property_id,),
            )
        return cur.fetchall()


def update_row_note(row_id: int, note_text: str) -> dict | None:
    """Persist a note into the import row's raw_json."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE import_row
            SET raw_json = raw_json || %s
            WHERE row_id = %s
            RETURNING *
            """,
            (Json({"note_text": note_text}), row_id),
        )
        return cur.fetchone()


def resolve_import_row(row_id: int) -> dict | None:
    """Mark an import row as resolved."""
    with get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE import_row SET resolved_at = NOW()
            WHERE row_id = %s AND resolved_at IS NULL
            RETURNING *
            """,
            (row_id,),
        )
        return cur.fetchone()

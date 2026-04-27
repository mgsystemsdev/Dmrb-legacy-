"""Migration runner — applies schema and incremental migrations at startup.

This module is the only place that knows about migration ordering and
detection logic. It is intentionally separate from connection management.

Call :func:`ensure_database_ready` once at application startup (currently
via ``ui/data/backend.py`` → ``bootstrap_backend()``).
"""

from __future__ import annotations

from pathlib import Path

from db.connection import get_connection

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def ensure_database_ready() -> None:
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'property'
            )
            """
        )
        initialized = cursor.fetchone()[0]
        if not initialized:
            cursor.execute(schema_sql)
        # Apply migration 002 (unit_movings) if the table is missing
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'unit_movings'
            )
            """
        )
        if not cursor.fetchone()[0]:
            migration_002 = (_MIGRATIONS_DIR / "002_unit_movings.sql").read_text(encoding="utf-8")
            cursor.execute(migration_002)
        # Apply migration 003 (import pipeline fields) if missing_moveout_count column is absent
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'turnover'
                  AND column_name = 'missing_moveout_count'
            )
            """
        )
        if not cursor.fetchone()[0]:
            migration_003 = (_MIGRATIONS_DIR / "003_import_pipeline_fields.sql").read_text(
                encoding="utf-8"
            )
            cursor.execute(migration_003)
        # Apply migration 004 (import_row.resolved_at) if the column is missing
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'import_row'
                  AND column_name = 'resolved_at'
            )
            """
        )
        if not cursor.fetchone()[0]:
            migration_004 = (_MIGRATIONS_DIR / "004_import_row_resolved.sql").read_text(
                encoding="utf-8"
            )
            cursor.execute(migration_004)
        # Apply migration 005 (phase_scope) if the table is missing (e.g. existing DBs)
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'phase_scope'
            )
            """
        )
        if not cursor.fetchone()[0]:
            migration_005 = (_MIGRATIONS_DIR / "005_phase_scope.sql").read_text(encoding="utf-8")
            cursor.execute(migration_005)
        # Apply migration 006 (system_settings) if the table is missing
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'system_settings'
            )
            """
        )
        if not cursor.fetchone()[0]:
            migration_006 = (_MIGRATIONS_DIR / "006_system_settings.sql").read_text(
                encoding="utf-8"
            )
            cursor.execute(migration_006)
        # Seed task_template when empty so turnovers get auto-created tasks (run 007 once)
        cursor.execute(
            "SELECT (SELECT COUNT(*) FROM phase) > 0 AND (SELECT COUNT(*) FROM task_template) = 0"
        )
        if cursor.fetchone()[0]:
            migration_007 = (_MIGRATIONS_DIR / "007_seed_task_templates.sql").read_text(
                encoding="utf-8"
            )
            cursor.execute(migration_007)
        # Apply migration 008 (drop manager_confirmed_at) if the column still exists
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'task'
                  AND column_name = 'manager_confirmed_at'
            )
            """
        )
        if cursor.fetchone()[0]:
            migration_008 = (_MIGRATIONS_DIR / "008_drop_manager_confirmed_at.sql").read_text(
                encoding="utf-8"
            )
            cursor.execute(migration_008)
        # Apply migration 009 (add completed_date) if the column is missing
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'task'
                  AND column_name = 'completed_date'
            )
            """
        )
        if not cursor.fetchone()[0]:
            migration_009 = (_MIGRATIONS_DIR / "009_add_task_completed_date.sql").read_text(
                encoding="utf-8"
            )
            cursor.execute(migration_009)
        # Apply migration 010 (unit_on_notice_snapshot) if the table is missing
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'unit_on_notice_snapshot'
            )
            """
        )
        if not cursor.fetchone()[0]:
            migration_010 = (_MIGRATIONS_DIR / "010_unit_on_notice_snapshot.sql").read_text(
                encoding="utf-8"
            )
            cursor.execute(migration_010)
        # Apply migration 011 (unit_occupancy_global) if the table is missing
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'unit_occupancy_global'
            )
            """
        )
        if not cursor.fetchone()[0]:
            migration_011 = (_MIGRATIONS_DIR / "011_unit_occupancy_global.sql").read_text(
                encoding="utf-8"
            )
            cursor.execute(migration_011)
        # Apply migration 012 (app_user) if the table is missing
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'app_user'
            )
            """
        )
        if not cursor.fetchone()[0]:
            migration_012 = (_MIGRATIONS_DIR / "012_app_user.sql").read_text(encoding="utf-8")
            cursor.execute(migration_012)
        # Apply migration 013 (wd_notified_at, wd_installed_at) if the columns are missing
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'turnover'
                  AND column_name = 'wd_notified_at'
            )
            """
        )
        if not cursor.fetchone()[0]:
            migration_013 = (_MIGRATIONS_DIR / "013_add_wd_tracking.sql").read_text(
                encoding="utf-8"
            )
            cursor.execute(migration_013)
        # Apply migration 014 (lifecycle_event) if the table is missing
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'lifecycle_event'
            )
            """
        )
        if not cursor.fetchone()[0]:
            migration_014 = (_MIGRATIONS_DIR / "014_lifecycle_event.sql").read_text(
                encoding="utf-8"
            )
            cursor.execute(migration_014)
        # Apply migration 015 (task_fsm) if skip_allowed column is absent from task
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'task'
                  AND column_name = 'skip_allowed'
            )
            """
        )
        if not cursor.fetchone()[0]:
            migration_015 = (_MIGRATIONS_DIR / "015_task_fsm.sql").read_text(encoding="utf-8")
            cursor.execute(migration_015)
        # Apply migration 016 (phase_scope per user) if the partial unique index is missing
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'phase_scope_property_global_uq'
            )
            """
        )
        if not cursor.fetchone()[0]:
            migration_016 = (_MIGRATIONS_DIR / "016_phase_scope_per_user.sql").read_text(
                encoding="utf-8"
            )
            cursor.execute(migration_016)
        # Apply migration 017 (unit.floor_plan, unit.gross_sq_ft) if either column is missing
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'unit'
                  AND column_name = 'floor_plan'
            )
            AND EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'unit'
                  AND column_name = 'gross_sq_ft'
            )
            """
        )
        if not cursor.fetchone()[0]:
            migration_017 = (_MIGRATIONS_DIR / "017_add_unit_fields.sql").read_text(
                encoding="utf-8"
            )
            cursor.execute(migration_017)

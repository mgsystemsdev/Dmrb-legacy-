#!/usr/bin/env python3
"""Completed-date consistency check (Full Regression Audit follow-up).

Read-only. Finds tasks with execution_status = 'COMPLETED' and completed_date IS NULL.
Such rows can exist if they were completed before the refactor that added completed_date.
Run from project root. Requires DATABASE_URL.

Exit code: 0 if no inconsistent rows; 1 if any found (or on error).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    from db.connection import get_connection
    from psycopg2.extras import RealDictCursor

    conn = get_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT task_id, turnover_id, task_type, execution_status,
                   vendor_completed_at, completed_date
            FROM task
            WHERE execution_status = 'COMPLETED' AND completed_date IS NULL
            ORDER BY task_id
            """
        )
        rows = cur.fetchall()

    if not rows:
        print("COMPLETED_DATE_CONSISTENCY: PASS (no COMPLETED tasks with null completed_date)")
        return 0

    print("COMPLETED_DATE_CONSISTENCY: FAIL")
    print(f"  Found {len(rows)} task(s) with execution_status = 'COMPLETED' and completed_date IS NULL:")
    for r in rows:
        print(f"    task_id={r['task_id']} turnover_id={r['turnover_id']} task_type={r['task_type']!r} vendor_completed_at={r['vendor_completed_at']}")
    print("  Optional: backfill completed_date from vendor_completed_at::date for these tasks.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

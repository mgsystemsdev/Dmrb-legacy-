#!/usr/bin/env python3
"""Run task_template count/listing using app config. Usage: python scripts/check_task_templates.py"""

from __future__ import annotations

import os
import re
from pathlib import Path


def _get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        text = secrets_path.read_text()
        m = re.search(r'DATABASE_URL\s*=\s*["\']([^"\']+)["\']', text)
        if m:
            return m.group(1)
    return ""


def main() -> None:
    url = _get_database_url()
    if not url:
        print("DATABASE_URL not found. Set it in .env or .streamlit/secrets.toml")
        return
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS task_template_rows FROM task_template")
            row = cur.fetchone()
            print("task_template row count:", row["task_template_rows"])
            cur.execute(
                "SELECT phase_id, task_type, sort_order, offset_days_from_move_out FROM task_template ORDER BY phase_id, sort_order"
            )
            rows = cur.fetchall()
            if rows:
                print("\nTemplates (phase_id, task_type, sort_order, offset_days):")
                for r in rows:
                    print(" ", r)
            else:
                print("(table is empty)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

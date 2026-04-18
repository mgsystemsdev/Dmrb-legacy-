#!/usr/bin/env python3
"""Phase 5 — Import Automation Layer: run once daily at midnight.

1. Transition open turnovers from On Notice → Vacant Not Ready when available_date has arrived.
2. Create new turnovers from unit_on_notice_snapshot when available_date <= today.

Requires DATABASE_URL (env or .streamlit/secrets.toml).
Usage:
  python scripts/run_midnight_automation.py
  python scripts/run_midnight_automation.py --date 2026-03-16
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    from config.settings import get_setting

    if not get_setting("DATABASE_URL"):
        print(
            "DATABASE_URL is not set. Set it in the environment or .streamlit/secrets.toml"
        )
        return 1

    parser = argparse.ArgumentParser(
        description="Run Import Automation Layer (On Notice → Vacant Not Ready; create from snapshot)."
    )
    parser.add_argument(
        "--date",
        type=str,
        metavar="YYYY-MM-DD",
        help="Reference date (default: today).",
    )
    args = parser.parse_args()

    today = date.today()
    if args.date:
        try:
            today = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print("Invalid --date; use YYYY-MM-DD")
            return 1

    from services.automation.lifecycle_automation_service import run_midnight_automation

    result = run_midnight_automation(today=today)
    tr = result["transitions"]
    cr = result["on_notice_created"]

    print(f"date={result['today']}")
    print(
        f"transitions: {tr['total_transitioned']} | on_notice_created: {cr['total_created']}"
    )
    for err in result["errors"]:
        print(f"  error: {err}")

    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())

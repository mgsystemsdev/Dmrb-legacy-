#!/usr/bin/env python3
"""Layer 3 — Backfill pipeline tasks for open turnovers with zero tasks.

Run from project root. Requires DATABASE_URL (env or .streamlit/secrets.toml).
Usage:
  python scripts/backfill_turnover_tasks.py
  python scripts/backfill_turnover_tasks.py --property-id 1
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    from config.settings import get_setting

    if not get_setting("DATABASE_URL"):
        print("DATABASE_URL is not set. Set it in the environment or .streamlit/secrets.toml")
        return 1

    parser = argparse.ArgumentParser(description="Backfill pipeline tasks for open turnovers with zero tasks.")
    parser.add_argument("--property-id", type=int, metavar="N", help="Run only for this property; omit to run all.")
    args = parser.parse_args()

    from services import turnover_service

    if args.property_id is not None:
        result = turnover_service.backfill_tasks_for_property(args.property_id)
        print(f"repaired={result['repaired']} skipped={result['skipped']} errors={len(result['errors'])}")
        for err in result["errors"]:
            print(f"  {err}")
        return 1 if result["errors"] else 0

    result = turnover_service.backfill_tasks_all_properties()
    print(
        f"total_repaired={result['total_repaired']} total_skipped={result['total_skipped']} errors={len(result['errors'])}"
    )
    for err in result["errors"]:
        print(f"  {err}")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())

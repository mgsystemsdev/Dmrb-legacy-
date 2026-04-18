#!/usr/bin/env python3
"""Step 7 — Data consistency: recompute domain values for one turnover and compare to board.

Read-only. Run from project root. Requires DATABASE_URL.
"""
from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    from db.repository import task_repository, turnover_repository
    from domain import readiness, sla, turnover_lifecycle
    from domain.priority_engine import derive_priority_from_agreements
    from services import board_service, scope_service
    from api.presentation.formatting import qc_label

    property_id = 1
    today = date.today()
    phase_scope = scope_service.get_phase_scope(property_id)
    board = board_service.get_board(property_id, today=today, phase_scope=phase_scope)
    if not board:
        print("DATA_CONSISTENCY: SKIP (no board items)")
        return 0

    item = board[0]
    turnover_id = item["turnover"]["turnover_id"]
    turnover = turnover_repository.get_by_id(turnover_id)
    if not turnover:
        print("DATA_CONSISTENCY: SKIP (turnover not found)")
        return 0

    tasks = task_repository.get_by_turnover(turnover_id)

    # Recompute priority via same pipeline as board: agreements first, then derive
    agreements_recomputed = board_service.evaluate_turnover_agreements(
        turnover, tasks, today
    )
    priority_recomputed = derive_priority_from_agreements(agreements_recomputed)

    recomputed = {
        "readiness_state": readiness.readiness_state(tasks),
        "days_since_move_out": turnover_lifecycle.days_since_move_out(turnover, today),
        "days_to_be_ready": turnover_lifecycle.days_to_be_ready(turnover, tasks, today),
        "sla_risk_level": sla.sla_risk(turnover, today),
        "priority": priority_recomputed,
        "qc_label": qc_label(tasks),
    }

    item = board[0]

    mismatches = []
    if item["readiness"]["state"] != recomputed["readiness_state"]:
        mismatches.append(("readiness.state", item["readiness"]["state"], recomputed["readiness_state"]))
    if item["turnover"].get("days_since_move_out") != recomputed["days_since_move_out"]:
        mismatches.append(("days_since_move_out", item["turnover"].get("days_since_move_out"), recomputed["days_since_move_out"]))
    if item["turnover"].get("days_to_be_ready") != recomputed["days_to_be_ready"]:
        mismatches.append(("days_to_be_ready", item["turnover"].get("days_to_be_ready"), recomputed["days_to_be_ready"]))
    if item["sla"].get("risk_level") != recomputed["sla_risk_level"]:
        mismatches.append(("sla.risk_level", item["sla"].get("risk_level"), recomputed["sla_risk_level"]))
    if item["priority"] != recomputed["priority"]:
        mismatches.append(("priority", item["priority"], recomputed["priority"]))

    if mismatches:
        print("DATA_CONSISTENCY: FAIL")
        for field, board_val, recomputed_val in mismatches:
            print(f"  {field}: board={board_val!r} recomputed={recomputed_val!r}")
        return 1
    print("DATA_CONSISTENCY: PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())

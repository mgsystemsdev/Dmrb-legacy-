# Phase 3 Guard Rails — Implementation Report

**Date:** 2026-03-16

## Where the guard rail logic was added

- **File:** [services/board_service.py](services/board_service.py)
- **New helpers:**
  - **`_evaluation_gate(turnover, today)`** — Returns `"skip_evaluation"`, `"vacant_ready"`, or `None` in this order: (1) `canceled_at` set → skip, (2) `move_out_date` is None → skip, (3) `lifecycle_phase == PHASE_VACANT_READY` → vacant_ready, else `None`.
  - **`_build_healthy_board_item(...)`** — Builds a board item with healthy defaults (priority NORMAL, sla OK, readiness READY, no move-in pressure) when the gate returns skip or vacant_ready. For skip, turnover is enriched with phase `PHASE_PRE_NOTICE` and null deltas; for vacant_ready, full lifecycle deltas are computed.
- **Integration:** In `get_board()`, after loading tasks, risks, and notes for each turnover, the code calls `_evaluation_gate(turnover, today)`. If the result is `"skip_evaluation"` or `"vacant_ready"`, it appends the result of `_build_healthy_board_item(...)` and continues; otherwise it runs the existing pipeline (lifecycle, readiness, SLA, priority, sort key).

## Confirmation that agreement checks run after guard rails

- Agreement logic (priority engine, SLA, readiness, and thus inspection/move-in/plan checks) is **only** run when `_evaluation_gate` returns `None`.
- When the gate returns `"skip_evaluation"` or `"vacant_ready"`, the board item is built via `_build_healthy_board_item` with fixed healthy values; `priority_level`, `sla_risk`, `readiness_state`, and related domain calls are not executed for that turnover.

## Confirmation that Vacant Ready units display all green dots

- When the gate returns `"vacant_ready"`, the same healthy board item is built: `priority="NORMAL"`, `sla.risk_level="OK"`, `readiness.state="READY"`, `move_in_pressure=None`. So `has_any_breach(item)` is False and the Flag Bridge table shows no red dots (Viol, Insp, SLA, MI, Plan all show as not breached). The unit still appears in the Flag Bridge table with all dots green.

## Verification (tests)

- **Scenario A — Vacant Ready:** `test_guard_rail_vacant_ready_item_has_no_breach` — Board built with a single Vacant Ready turnover; item has priority NORMAL, has_any_breach False, lifecycle_phase VACANT_READY.
- **Scenario B — No move-out:** `test_guard_rail_no_move_out_produces_no_violations` — Board built with turnover with `move_out_date` None; item has no violations, flag bridge metrics show 0 violations and 0 units_with_breach.
- **Scenario C — Cancelled:** `test_guard_rail_cancelled_turnover_produces_no_violations` — Board built with turnover with `canceled_at` set; item has healthy defaults and has_any_breach False.
- **Scenario D — Normal turnover:** `test_guard_rail_normal_turnover_still_evaluated` — Normal turnover (move-out set, not cancelled, not Vacant Ready) runs the full pipeline; item has priority/readiness/sla/lifecycle_phase from domain.
- **`_evaluation_gate` unit tests:** `test_evaluation_gate_returns_skip_when_canceled`, `test_evaluation_gate_returns_skip_when_no_move_out`, `test_evaluation_gate_returns_vacant_ready_when_manual_ready`, `test_evaluation_gate_returns_none_when_normal_turnover`.

All 22 tests in `tests/services/test_board_service.py` pass.

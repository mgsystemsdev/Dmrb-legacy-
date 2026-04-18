# Phase 5: Derived Urgency from Agreements — Implementation Report

## Where priority derivation was implemented

- **Domain:** [domain/priority_engine.py](domain/priority_engine.py)
  - `derive_priority_from_agreements(agreements) -> str` — maps agreement flags to a single priority label in severity order (move_in > sla > inspection > plan > NORMAL).
  - `urgency_sort_key(priority, turnover, today) -> tuple` — sort key from derived priority and days-to-move-in only.
  - `PLAN_DELAY` constant and `PRIORITY_ORDER` extended to include `PLAN_DELAY`.

- **Board integration:** [services/board_service.py](services/board_service.py)
  - In `get_board()` (full-evaluation path): agreements are computed first via `evaluate_turnover_agreements(turnover, tasks, today, ...)`, then `priority = derive_priority_from_agreements(agreements)`, then `sort_key = urgency_sort_key(priority, turnover, today)`. Item is built with `agreements`, `priority`, and `_sort_key`.
  - In `_build_healthy_board_item()`: `agreements = AGREEMENTS_ALL_GREEN`, `priority = "NORMAL"`, `_sort_key = urgency_sort_key("NORMAL", turnover, today)`.

## Confirmation that agreement evaluation runs before priority

- In `get_board()`, for every item that is fully evaluated (gate is `None`), the sequence is:
  1. `agreements = evaluate_turnover_agreements(turnover, tasks, today, sla_threshold_days=AGREEMENT_SLA_DAYS)`
  2. `priority = derive_priority_from_agreements(agreements)`
  3. `sort_key = urgency_sort_key(priority, turnover, today)`
- Priority is never computed from turnover/tasks directly in the board build; it is always derived from the agreements dict. The healthy/skip path sets agreements to all GREEN and priority to NORMAL without calling the legacy `priority_level`.

## Confirmation that priority does not determine flags

- Priority is never passed into the agreement evaluator. `evaluate_turnover_agreements()` takes only `turnover`, `tasks`, `today`, and `sla_threshold_days`; it does not receive or use `priority`.
- All flag/count logic (`get_flag_counts`, `get_flag_units`, `filter_by_flag_category`, `has_any_breach`, `get_flag_bridge_metrics`) uses `item["agreements"]` when present as the canonical source; they use `item["priority"]` only as a summary label for display and filtering. Priority is output-only from the agreements pipeline.

## Example board item (agreements + priority)

**Move-in violation (move_in RED → MOVE_IN_DANGER):**

```json
{
  "agreements": {
    "inspection": "GREEN",
    "sla": "GREEN",
    "move_in": "RED",
    "plan": "GREEN",
    "viol": "RED"
  },
  "priority": "MOVE_IN_DANGER"
}
```

**Healthy pipeline (all GREEN → NORMAL):**

```json
{
  "agreements": {
    "inspection": "GREEN",
    "sla": "GREEN",
    "move_in": "GREEN",
    "plan": "GREEN",
    "viol": "GREEN"
  },
  "priority": "NORMAL"
}
```

## Verification

- **Unit tests:** [tests/domain/test_priority.py](tests/domain/test_priority.py) — `TestDerivePriorityFromAgreements` (Cases 1–5 plus severity order) and `TestUrgencySortKey` (ordering and rank).
- **Service tests:** [tests/services/test_board_service.py](tests/services/test_board_service.py) — `test_board_priority_derived_from_agreements` asserts that for every board item, `item["priority"] == derive_priority_from_agreements(item["agreements"])`.
- **Consistency script:** [scripts/domain_data_consistency_check.py](scripts/domain_data_consistency_check.py) recomputes priority via `evaluate_turnover_agreements` + `derive_priority_from_agreements` and compares to board output; run reports `DATA_CONSISTENCY: PASS`.

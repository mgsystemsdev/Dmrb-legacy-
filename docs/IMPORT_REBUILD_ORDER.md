# Import rebuild order (clean database contract)

Operational law for rebuilding DMRB Legacy from CSV imports after a **clean** database (schema applied, no operational rows except a **property**). Complements [REBUILD_RECONCILIATION_RUNBOOK.md](REBUILD_RECONCILIATION_RUNBOOK.md).

## Prerequisites before any import

- Database schema/migrations applied.
- At least one **property** row exists (imports are keyed by `property_id`).
- DB writes enabled when required (Streamlit Admin toggle or headless policy).
- Default task templates are created when phases are created (`property_service.create_phase`).

## Report types and bootstrap behavior

| Type | Creates units | Creates open turnovers | Notes |
|------|---------------|------------------------|--------|
| **MOVE_OUTS** | Yes | Yes (when no open turnover) | **Preferred first** import for predictable rebuild. |
| **AVAILABLE_UNITS** | Conditional | Conditional | Depends on row **Status** (vacant creation vs needs existing unit). Not reliable as the only first file for all portfolios. |
| **PENDING_MOVE_INS** | Yes | **No** | **Requires** an open turnover per unit; otherwise rows become **CONFLICT** (`MOVE_IN_WITHOUT_OPEN_TURNOVER`). |
| **PENDING_FAS** | No (placeholder) | No | Does not bootstrap board/turnovers today. |

## Recommended sequence (clean rebuild)

1. **MOVE_OUTS** first (or **AVAILABLE_UNITS** only if your file’s statuses create every needed unit and turnover).
2. **AVAILABLE_UNITS** as needed for availability / vacancy reconciliation (often after or alongside move-out driven state).
3. **PENDING_MOVE_INS** after open turnovers exist for units in the file.
4. **PENDING_FAS** only when you accept placeholder behavior (no operational entity creation).

## After imports

Run **`run_board_reconciliation_for_property`** (or load the board / `get_board`) per the reconciliation runbook. **Imports alone** are not guaranteed to match post-reconciliation board truth.

## Orchestrator safeguards

- **`rebuild_order_warning`:** If you import **PENDING_MOVE_INS** while the property has **zero** open turnovers, a warning is added to import **diagnostics** and a WARNING is logged. The import still runs unless strict mode is on.
- **`STRICT_IMPORT_REBUILD_ORDER`:** If set to a truthy value (`1`, `true`, `yes`, `on`), the same condition causes the import to **fail before** starting a batch (no `COMPLETED` batch of all conflicts). Use for automated clean-slate pipelines; leave off for normal operations and partial re-imports.

Environment variable or Streamlit secrets (same as other `get_setting` keys).

## Rebuild complete (slice)

- Expected **SUCCESS** / row outcomes for each file.
- Reconciliation executed for the property.
- No unexpected `board_reconciliation_failed` log lines.
- Board/export checks match expectations for scope.

## Never assume

- Import order does not matter.
- **PENDING_MOVE_INS** creates turnovers.
- **PENDING_FAS** builds operational state.
- Skipping reconciliation matches production board truth.

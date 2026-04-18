# Rebuild and board reconciliation (runbook)

Operational contract for DMRB Legacy when rebuilding from imports (e.g. clean Supabase after schema apply).

## When rebuild starts

After migrations/schema exist and at least one **property** row exists. Imports require a `property_id`; the import pipeline does not create properties.

## Prerequisites

- Property and phase/task-template policy (default templates seed on `property_service.create_phase`).
- DB writes enabled when using Streamlit Admin toggle (headless/scripts: see `write_guard`).

## Imports

Run the **minimum valid sequence** for your portfolio. Order matters (e.g. turnover-creating reports before Pending Move-Ins). See **[IMPORT_REBUILD_ORDER.md](IMPORT_REBUILD_ORDER.md)** for the full contract, diagnostics, and optional strict mode.

## When reconciliation runs

**After** imports for a property are complete for the current slice, **before** treating database state as “board-true.”

You satisfy reconciliation by **either**:

1. Calling **`services.board_reconciliation.run_board_reconciliation_for_property(property_id, today=..., phase_ids=...)`** with the same `today` and phase scope you use for the board, or  
2. Calling **`board_service.get_board`** / **`get_board_view`** / **`get_board_summary`** / **`get_board_metrics`** without a pre-built `board=` (they run the same reconciliation inside `get_board`).

## System considered ready

Reconciliation has completed; check application logs for `board_reconciliation_failed` if any step threw (failures are logged, not re-raised). A second `get_board` with the same `today` and imports unchanged should be stable except for date-sensitive automation when `today` changes.

## Never assume

- Imports alone match post-board DB state.  
- Skipping reconciliation matches production board truth.  
- `today` is irrelevant (On Notice and DV-window automation depend on it).

---

## Verification checklist (post-implementation)

Use after a clean DB rebuild or when validating the contract.

1. **Clean DB path:** Create property, run valid imports, then call `run_board_reconciliation_for_property` once (or `get_board` once). Record open turnover count and task counts per turnover.
2. **Idempotency:** Run reconciliation again with the same `today`. Expect no duplicate tasks per turnover and no duplicate open turnovers per unit (existing DB constraints + service guards).
3. **Import → reconcile → board:** Where Available Units / On Notice healing applies, compare board-relevant fields before vs after the first reconciliation pass; a second `get_board` without new data should not change row counts.
4. **Headless:** From a Python shell or script (no Streamlit UI), run: imports or fixtures → `run_board_reconciliation_for_property` → `get_board`. Result should match opening the board once for that property/scope.

## Code reference

- Orchestrator: [`services/board_reconciliation.py`](../services/board_reconciliation.py) — `run_board_reconciliation_for_property`
- Invoked from: [`services/board_service.py`](../services/board_service.py) — `get_board` (lazy import to avoid circular imports)

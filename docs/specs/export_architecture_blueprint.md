# Export Architecture Blueprint

Last updated: 2026-03-15
Status: Current-state placeholder plus target direction

## 1. Current Implementation State

The Export Reports surface exists in `ui/screens/export_reports.py`, but export generation is not implemented.

What exists today:

- an Export Reports page
- a "Prepare Export Files" button
- **Weekly Summary (TXT):** `services/export_service.py` builds `Weekly_Summary.txt` from board service data; download wired after Prepare
- placeholder downloads for Final Report, DMRB Report, chart, and ZIP (empty payloads)

What does not exist yet:

- workbook/chart generation and ZIP packaging
- tests for Excel/chart/ZIP exports (Weekly Summary covered in `tests/services/test_export_service.py`)

Any older document that describes a completed export subsystem should be treated as target-state design, not current implementation.

## 2. Current UI Behavior

The current page says:

- exports always include all open turnovers regardless of current screen filters

That is only placeholder messaging.
It should not be treated as a final architectural decision.

## 3. Correct Direction for Future Export Scope

The intended operational rule is:

- exports should respect the active operational phase scope for the selected property
- imports should remain full-property

Because export generation is not yet implemented, that rule has not been enforced in code yet.

## 4. Recommended Future Architecture

When implemented, exports should remain renderers over existing board/service data rather than a parallel business-logic system.

Recommended flow:

1. load the operational dataset from shared services
2. apply active property and phase scope
3. flatten rows for export rendering
4. build files
5. hand byte payloads back to the UI

## 5. Likely Shared Data Sources

The eventual export implementation should rely on existing service outputs where possible:

- `services.board_service.get_board()`
- `services.board_service.get_board_metrics()`
- `services.board_service.get_flag_counts()`

That keeps exports aligned with board calculations for:

- lifecycle
- readiness
- SLA risk
- priority
- flag counts

## 6. Open Decisions That Still Need Implementation

- exact export file inventory
- export file formats and naming
- scoped vs full-property output defaults
- packaging strategy
- download caching / regeneration behavior
- whether export rows come directly from board items or from a dedicated export flattener

## 7. Documentation Rule Going Forward

Until real export services exist, the export subsystem should be documented as:

- screen exists
- generation is placeholder
- final scope rule should be phase-aware and property-aware

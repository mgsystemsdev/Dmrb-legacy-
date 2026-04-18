# DMRB Import Pipeline Specification

Last updated: 2026-03-15
Status: Reflects current implementation, including placeholders

## 1. Purpose

The import pipeline ingests PMS report files, records a durable import audit trail, and applies allowed changes to operational data.

The code path is centered on:

- `services/import_service.py`
- `services/imports/orchestrator.py`
- `services/imports/*.py`
- `db/repository/import_repository.py`

## 2. Core Principles

### Reports are signals, not blind commands

Imports propose updates.
DMRB applies them according to report role, override rules, and current turnover state.

### Every row gets a recorded outcome

The pipeline writes an `import_row` for every processed row.

### Imports are property-wide

Current phase selection in the UI does not scope ingestion.
The orchestrator has a `VALID_PHASES` hook, but it is currently `None`, so all phases pass through.

## 3. Pipeline Flow

Current orchestration flow in `services/imports/orchestrator.py`:

1. read file bytes
2. compute checksum
3. perform duplicate detection
4. validate file type
5. validate schema
6. parse CSV rows
7. apply optional phase filtering
8. create and mark batch as processing
9. delegate to report-specific service
10. complete or fail the batch

## 4. Duplicate Detection Reality

The current implementation does duplicate detection before the real batch is created.

Important implementation detail:

- for non-`AVAILABLE_UNITS` reports, the orchestrator calls `import_service.start_batch()` once as a duplicate probe and then again to create the real batch
- the code comment says the probe batch is "not persisted", but `start_batch()` does insert a batch row

This means the docs should treat duplicate probing as an active stabilization concern, not a solved behavior.

`AVAILABLE_UNITS` is intentionally different:

- its checksum is salted with a timestamp so the same file can be re-imported

## 5. Row Outcome Model

Current row statuses used by the implementation:

- `OK`
- `INVALID`
- `CONFLICT`
- `IGNORED`
- `SKIPPED_OVERRIDE`

Conflict reasons and validation reasons are recorded in `conflict_reason` when the row is conflict-like.

Each row also stores:

- normalized unit code when available
- parsed move-out / move-in dates when available
- original source row in `raw_json`

## 6. Shared Import Rules

### Unit normalization and creation

Shared helpers in `services/imports/common.py`:

- normalize unit code
- parse dates
- sanitize row payloads for JSON
- resolve existing units
- create missing phases/buildings/units when needed

### Manual override rule

`domain/manual_override.py` centralizes the rule:

- no override: accept import value
- override exists and incoming equals current: accept and clear override
- override exists and incoming differs: skip the import value

This rule is implemented in:

- `move_outs_service.py`
- `move_ins_service.py`
- `available_units_service.py`

## 7. Implemented Report Roles

### 7.1 MOVE_OUTS

Current behavior:

- validates move-out date
- resolves or creates unit
- creates a new turnover when none exists
- otherwise updates scheduled move-out date with override protection
- updates `move_out_date` too when there is no legal confirmation source
- tracks `missing_moveout_count`
- auto-cancels turnovers after repeated absence from Move Outs, but only for turnovers that had a `scheduled_move_out_date`

Important current note:

- cancellation logic is implemented through `domain.move_out_absence.should_cancel_turnover()`

### 7.2 PENDING_MOVE_INS

Current behavior:

- validates move-in date
- resolves or creates unit
- does not create turnovers
- records `CONFLICT` when no open turnover exists
- updates `move_in_date` with override protection when an open turnover exists

### 7.3 AVAILABLE_UNITS

Current behavior:

- normalizes status and parses dates
- resolves or creates unit only when the status allows turnover creation
- can create fallback turnovers for vacancy statuses when an available date exists
- updates `report_ready_date`, `available_date`, and `availability_status`
- respects ready-date and status manual overrides
- clears stale vacancy `availability_status` for open turnovers whose units disappear from the current file, unless blocked by manual override

Important current limitation:

- there is no separate override timestamp for `available_date`; that field always updates when present

### 7.4 PENDING_FAS

Current behavior is placeholder only.

What it does today:

- parses the rows
- records them as `OK`
- stores the parsed move-out date in the import row

What it does not do yet:

- confirm legal move-out date on turnovers
- set `legal_confirmation_source`
- set `legal_confirmed_at`
- update `confirmed_move_out_date`
- reconcile SLA based on the confirmed date

Older docs that describe full FAS confirmation logic are aspirational, not current-state accurate.

## 8. Diagnostics and Repair Surfaces

The import subsystem currently exposes three operational UI surfaces:

### Import Reports

`ui/screens/import_console.py`

Current purpose:

- run imports
- preview latest batch status per report type
- inspect latest imported rows

### Report Operations

`ui/screens/import_reports.py`

Current purpose:

- override conflict resolution
- invalid-data correction
- import diagnostics by batch

### Repair Reports

`ui/screens/repair_reports.py`

Current purpose:

- Missing Move-Out queue
- FAS Tracker note management

## 9. Current Risks and Gaps

- duplicate probe batch behavior needs cleanup
- Pending FAS business logic is still placeholder
- import outcomes are durable, but end-to-end import tests are still light
- imports create units/phases/buildings dynamically, which is useful operationally but should be explicitly validated against future multi-property assumptions

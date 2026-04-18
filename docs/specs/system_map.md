# DMRB System Map

Last updated: 2026-03-15
Status: Current on-disk module map

## 1. Purpose

This document maps the repository as it exists today.

It is not a target-state folder diagram. It is the current implementation map, including transitional areas that still need cleanup.

## 2. Top-Level Structure

```text
DRMB_PROD/
  app.py
  requirements.txt
  config/
  domain/
  services/
  application/
  db/
  ui/
  tests/
  docs/
  RAWW/
```

## 3. Entrypoint and Bootstrap

### `app.py`

Current responsibility:

- Streamlit page setup
- session-state initialization
- backend bootstrap
- sidebar rendering
- routing

### `ui/data/backend.py`

Current responsibility:

- cached call into `db.connection.ensure_database_ready()`

### `db/connection.py`

Current responsibility:

- resolve `DATABASE_URL`
- create the shared psycopg2 connection
- bootstrap schema from `db/schema.sql` if needed

This means bootstrap currently comes from schema execution, not a migration runner.

## 4. Domain Layer

Current `domain/` modules:

- `availability_status.py`: vacancy/readiness status helpers for Available Units imports
- `import_outcomes.py`: canonical import outcome/status/reason constants
- `manual_override.py`: pure rule for import-vs-manual override resolution
- `move_out_absence.py`: missing move-out cancellation rule
- `priority_engine.py`: board priority calculation and sorting helpers
- `readiness.py`: readiness state, blockers, completion helpers
- `sla.py`: SLA risk and timing calculations
- `turnover_lifecycle.py`: lifecycle phase and time delta calculations
- `unit_identity.py`: unit normalization, parsing, identity helpers

The domain layer is one of the cleaner parts of the repository and mostly matches the intended architecture.

## 5. Service Layer

Current top-level `services/` modules:

- `audit_service.py`
- `board_service.py`
- `import_service.py`
- `note_service.py`
- `property_service.py`
- `risk_service.py`
- `task_service.py`
- `turnover_service.py`
- `unit_movings_service.py`
- `unit_service.py`
- `write_guard.py`

### Report-operations services

`services/report_operations/` currently contains:

- `import_diagnostics_service.py`
- `invalid_data_service.py`
- `missing_move_out_service.py`
- `override_conflict_service.py`

### Import pipeline services

`services/imports/` currently contains:

- `available_units_service.py`
- `common.py`
- `move_ins_service.py`
- `move_outs_service.py`
- `orchestrator.py`
- `pending_fas_service.py`
- `validation/file_validator.py`
- `validation/schema_validator.py`

Important current reality:

- the service layer is the main orchestration layer
- the `application/` layer is not actively used for most flows
- services call repositories directly

## 6. Repository Layer

Current `db/repository/` modules:

- `audit_repository.py`
- `import_repository.py`
- `note_repository.py`
- `property_repository.py`
- `risk_repository.py`
- `task_repository.py`
- `turnover_repository.py`
- `unit_movings_repository.py`
- `unit_repository.py`

Current behavior differs from the original architecture docs in one important way:

- repositories fetch their own database connection through `db.connection.get_connection()`

So the current implementation is service-oriented, but not yet caller-injected at the repository boundary.

## 7. UI Layer

### Routing

`ui/router.py` routes these page keys:

- `board`
- `unit_detail`
- `import_reports`
- `flag_bridge`
- `add_turnover`
- `property_structure`
- `morning_workflow`
- `risk_radar`
- `ai_agent`
- `work_order_validator`
- `operations_schedule`
- `admin`
- `repair_reports`
- `import_console`
- `export_reports`

### Sidebar

`ui/components/sidebar.py` owns:

- property selection
- grouped navigation
- top flag shortcuts

### Screens

Current `ui/screens/` modules:

- `add_turnover.py`
- `admin.py`
- `ai_agent.py`
- `board.py`
- `export_reports.py`
- `flag_bridge.py`
- `import_console.py`
- `import_reports.py`
- `morning_workflow.py`
- `operations_schedule.py`
- `property_structure.py`
- `repair_reports.py`
- `risk_radar.py`
- `unit_detail.py`
- `work_order_validator.py`

### Shared UI modules

- `ui/components/board_table.py`
- `ui/components/filters.py`
- `ui/components/task_panel.py`
- `ui/helpers/formatting.py`
- `ui/state/constants.py`
- `ui/state/session.py`

## 8. Application Layer

`application/commands/` and `application/workflows/` exist, but are effectively placeholders right now.

Current reality:

- most operational flows are UI -> service directly
- the application layer should be treated as reserved architecture space, not an active dependency boundary

## 9. Tests

Current automated coverage exists in:

- `tests/domain/`
- `tests/services/`

There are tests for:

- lifecycle logic
- readiness logic
- SLA logic
- priority logic
- core board/task/turnover services

Notable current gap:

- no meaningful end-to-end import or UI tests

## 10. Documentation Layout

### Current docs intended as active specs

- `docs/specs/system_blueprint.md`
- `docs/specs/architecture_rules.md`
- `docs/specs/system_map.md`
- `docs/specs/canonical_data_model.md`
- `docs/specs/DMRB_IMPORT_PIPELINE_SPEC.md`
- `docs/specs/export_architecture_blueprint.md`
- `docs/specs/operational_priority.md`

### Historical or reference-only docs

- `docs/legacy/screens/`
- `docs/legacy/research/`

Those legacy docs remain useful for comparison and research, but they should not be treated as the canonical current-state source unless explicitly updated.

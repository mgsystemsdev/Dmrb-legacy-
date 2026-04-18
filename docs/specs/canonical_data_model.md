# Canonical Data Model

Last updated: 2026-03-15
Status: Reflects `db/schema.sql`

## 1. Design Philosophy

The database stores facts.
Derived operational values are computed in domain and service code.

Examples of stored facts:

- unit identity and hierarchy
- turnover dates and overrides
- tasks and notes
- risk flags and SLA events
- import batches and rows
- audit trail entries

Examples of computed values:

- lifecycle phase
- days since move-out
- days to be ready
- readiness summary
- board priority
- risk-radar score

## 2. Core Hierarchy

The core structural chain is:

`property -> phase -> building -> unit -> turnover`

Operational child records then hang off the turnover:

- tasks
- notes
- risk flags
- SLA events
- task overrides

## 3. Schema Snapshot

### Property

Table: `property`

Key fields:

- `property_id`
- `name`
- `created_at`
- `updated_at`

### Phase

Table: `phase`

Key fields:

- `phase_id`
- `property_id`
- `phase_code`
- `name`
- `created_at`
- `updated_at`

Important rule:

- unique per property on `(property_id, phase_code)`

### Building

Table: `building`

Key fields:

- `building_id`
- `property_id`
- `phase_id`
- `building_code`
- `name`
- `created_at`
- `updated_at`

Important rule:

- unique per phase on `(phase_id, building_code)`

### Unit

Table: `unit`

Key fields:

- `unit_id`
- `property_id`
- `phase_id`
- `building_id`
- `unit_code_raw`
- `unit_code_norm`
- `unit_identity_key`
- `floor_plan`
- `gross_sq_ft`
- `has_carpet`
- `has_wd_expected`
- `is_active`
- `created_at`
- `updated_at`

Important rules:

- unique per property on `(property_id, unit_code_norm)`
- unique per property on `(property_id, unit_identity_key)`

### Turnover

Table: `turnover`

Key fields:

- `turnover_id`
- `property_id`
- `unit_id`
- `move_out_date`
- `move_in_date`
- `report_ready_date`
- `available_date`
- `availability_status`
- `scheduled_move_out_date`
- `confirmed_move_out_date`
- `legal_confirmation_source`
- `legal_confirmed_at`
- `manual_ready_status`
- `manual_ready_confirmed_at`
- `closed_at`
- `canceled_at`
- `cancel_reason`
- `missing_moveout_count`
- `move_out_manual_override_at`
- `move_in_manual_override_at`
- `ready_manual_override_at`
- `status_manual_override_at`
- `created_at`
- `updated_at`

Important rules:

- one open turnover per unit through `ux_turnover_one_open`
- `manual_ready_status` is constrained to `On Notice`, `Vacant Not Ready`, `Vacant Ready`
- `closed_at` and `canceled_at` are mutually exclusive
- `move_in_date >= move_out_date` when move-in exists
- `available_date >= move_out_date` when available date exists

Note:

- `report_ready_date` is allowed to precede `move_out_date` in the active schema because pre-vacancy prep is allowed

### Task Template

Table: `task_template`

Key fields:

- `template_id`
- `property_id`
- `phase_id`
- `task_type`
- `sort_order`
- `offset_days_from_move_out`
- `required`
- `blocking`
- `is_active`
- `created_at`
- `updated_at`

Important rules:

- active uniqueness per phase/task type
- offset days must be `>= 1`

### Task

Table: `task`

Key fields:

- `task_id`
- `property_id`
- `turnover_id`
- `task_type`
- `scheduled_date`
- `vendor_due_date`
- `execution_status`
- `vendor_completed_at`
- `required`
- `blocking`
- `assignee`
- `created_at`
- `updated_at`

Important rules:

- unique task type per turnover
- execution status must be one of `NOT_STARTED`, `SCHEDULED`, `IN_PROGRESS`, `COMPLETED`
- completed tasks require `vendor_completed_at` (set when status becomes COMPLETED)

Task lifecycle: task created → execution progresses → execution becomes COMPLETED → `vendor_completed_at` recorded. Completion is determined solely by `execution_status = 'COMPLETED'` and `vendor_completed_at` timestamp.

### Note

Table: `note`

Key fields:

- `note_id`
- `property_id`
- `turnover_id`
- `severity`
- `text`
- `created_at`
- `updated_at`
- `resolved_at`

Severity values:

- `INFO`
- `WARNING`
- `CRITICAL`

### Risk Flag

Table: `risk_flag`

Key fields:

- `risk_id`
- `property_id`
- `turnover_id`
- `risk_type`
- `severity`
- `opened_at`
- `resolved_at`
- `created_at`
- `updated_at`

Important rule:

- one open risk of a given type per turnover

### SLA Event

Table: `sla_event`

Key fields:

- `sla_event_id`
- `property_id`
- `turnover_id`
- `breach_started_at`
- `breach_resolved_at`
- `threshold_days`
- `created_at`
- `updated_at`

Important rule:

- one open SLA breach event per turnover

### Audit Log

Table: `audit_log`

Key fields:

- `audit_id`
- `property_id`
- `entity_type`
- `entity_id`
- `field_name`
- `old_value`
- `new_value`
- `actor`
- `source`
- `changed_at`
- `created_at`

Important rule:

- append-only through the `prevent_mutation()` trigger

### Import Batch

Table: `import_batch`

Key fields:

- `batch_id`
- `property_id`
- `report_type`
- `checksum`
- `status`
- `record_count`
- `created_at`
- `updated_at`

### Import Row

Table: `import_row`

Key fields:

- `row_id`
- `property_id`
- `batch_id`
- `unit_code_raw`
- `unit_code_norm`
- `move_out_date`
- `move_in_date`
- `validation_status`
- `conflict_flag`
- `conflict_reason`
- `raw_json`
- `resolved_at`
- `created_at`
- `updated_at`

Validation statuses currently supported by schema:

- `OK`
- `INVALID`
- `CONFLICT`
- `IGNORED`
- `SKIPPED_OVERRIDE`

### Turnover Task Override

Table: `turnover_task_override`

Key fields:

- `property_id`
- `turnover_id`
- `task_type`
- `required_override`
- `blocking_override`
- `created_at`
- `updated_at`

### Unit Movings

Table: `unit_movings`

Key fields:

- `unit_movings_id`
- `unit_number`
- `moving_date`
- `created_at`

Purpose:

- supports the Work Order Validator workflow

## 4. Important Current Observations

- The schema is more complete than several older docs implied.
- The active schema includes override-tracking fields and task override storage.
- The active schema includes `unit_movings`, which is operationally important but easy to miss in older architecture writeups.
- The schema supports SLA persistence through `sla_event`, but the board still computes SLA state dynamically.

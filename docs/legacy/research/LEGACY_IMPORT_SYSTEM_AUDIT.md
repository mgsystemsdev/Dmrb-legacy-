# LEGACY IMPORT SYSTEM AUDIT

**Purpose:** Reverse-engineer business logic and workflows for MOVE_OUTS, MOVE_INS (PENDING_MOVE_INS), AVAILABLE_UNITS, and PENDING_FAS so they can be rebuilt cleanly in the new architecture (UI → Services → Domain → Repositories → PostgreSQL). Behavior is extracted; code is not copied.

---

## 1. Import Entry Points

| FILE | FUNCTION | PURPOSE |
|------|----------|---------|
| `ui/screens/admin.py` | `_run_import_for_report` | UI: file upload per report type, temp file write, calls apply workflow, commits, invalidates caches, displays result/diagnostics |
| `ui/screens/admin.py` | `apply_import_row_workflow` (via button) | Triggered by "Run … import" buttons; builds `ApplyImportRow` and invokes workflow |
| `application/workflows/write_workflows.py` | `apply_import_row_workflow` | Single orchestration entry: calls `import_service.import_report_file` with conn, report_type, file_path, property_id, db_path |
| `services/import_service.py` | (re-export) | Thin shim; re-exports `import_report_file` and constants from `services.imports.orchestrator` |
| `services/imports/orchestrator.py` | `import_report_file` | **Main entry:** checksum, optional NO_OP, file/schema validation, parse by report type, apply by report type, post-process (MOVE_OUTS only), reconciliation (AVAILABLE_UNITS only), optional DB backup |

**Report type constants:** `services/imports/constants.py` — `MOVE_OUTS`, `PENDING_MOVE_INS`, `AVAILABLE_UNITS`, `PENDING_FAS`, `DMRB`.

**Validation entry:** Before parsing, `imports.validation.file_validator.validate_import_file` and `imports.validation.schema_validator.validate_import_schema` are called; on failure an exception is raised and a FAILED batch is inserted.

---

## 2. Report Workflows

### High-level (all types)

```
User uploads file (Admin → Import console tab)
    ↓
UI writes to temp file, gets conn, calls apply_import_row_workflow(ApplyImportRow(...))
    ↓
import_report_file(conn, report_type, file_path, property_id, ...)
    ↓
Compute checksum (report_type + file bytes); AVAILABLE_UNITS: salt with timestamp so same file can be re-imported
    ↓
If report_type != AVAILABLE_UNITS and batch with same checksum exists → return NO_OP (no parse/apply)
    ↓
validate_import_file(report_type, file_path)  → file type, non-empty
    ↓
validate_import_schema(report_type, file_path) → required columns, required fields, date/numeric format per row
    ↓
Parse file (report-specific skiprows/columns) → list of row dicts; _filter_phase(rows) keeps only allowed phases
    ↓
Insert import_batch (SUCCESS, record_count = len(rows)), get batch_id
    ↓
Apply report-specific apply_*(conn, batch_id, rows, property_id, now_iso, actor, corr_id)
    ↓
Per-row: ensure unit, load open turnover, apply business rules, write import_row, update turnover/unit/task/audit as needed
    ↓
[MOVE_OUTS only] post_process_after_move_outs(conn, property_id, batch_id, seen_unit_ids, ...)
    ↓
[AVAILABLE_UNITS only] reconcile_available_units_readiness_from_latest(...); reconcile_available_units_vacancy_invariant(...)
    ↓
Optional DB backup if db_path and backup_dir provided
    ↓
Return { report_type, checksum, status, batch_id, record_count, applied_count, conflict_count, invalid_count, diagnostics }
```

### MOVE_OUTS

- **Parse:** CSV skip 6 rows; columns `Unit`, `Move-Out Date`. Normalize unit (raw, norm), parse date; filter by phase.
- **Apply:** For each row:
  - If Move-Out Date missing → INVALID, write import_row, invalid_count++, continue.
  - Ensure unit exists (`_ensure_unit`).
  - Get open turnover for unit.
  - **If open turnover exists:** If manual override on scheduled_move_out_date and incoming date matches current → clear override, update scheduled_move_out_date, last_seen_moveout_batch_id, missing_moveout_count=0, write import_row OK, applied_count++. If override and date differs → do not overwrite scheduled date; write skip audit; row outcome SKIPPED_OVERRIDE; write import_row. If no override: if no legal_confirmation_source and move_out_date differs from incoming → update move_out_date (correction); always align scheduled_move_out_date to import; update last_seen_moveout_batch_id, missing_moveout_count=0; write import_row OK, applied_count++. Add unit_id to seen_unit_ids.
  - **If no open turnover:** Create turnover via `find_or_create_turnover_for_unit` (which uses `turnover_service.create_turnover_and_reconcile` → insert turnover, instantiate tasks, SLA reconcile, risk reconcile). Set last_seen_moveout_batch_id, missing_moveout_count=0, scheduled_move_out_date on new turnover. Audit "created", "import:MOVE_OUTS". Write import_row OK, applied_count++, add to seen_unit_ids.
- **Post-process:** For all open turnovers in property: if unit in seen_unit_ids → set missing_moveout_count=0, last_seen_moveout_batch_id=batch_id. If unit not in seen_unit_ids → increment missing_moveout_count; if ≥ 2 → set canceled_at, cancel_reason "Move-out disappeared from report twice", audit.

### PENDING_MOVE_INS (Move-Ins)

- **Parse:** CSV skip 5 rows; columns `Unit`, `Move In Date`. Normalize unit, parse date; filter by phase.
- **Apply:** For each row:
  - Get unit by norm; if missing, create via `_ensure_unit` (so unit exists for later resolution).
  - Get open turnover. If none → CONFLICT, conflict_reason MOVE_IN_WITHOUT_OPEN_TURNOVER, write import_row, conflict_count++.
  - If open turnover: If move_in_manual_override_at set and incoming move_in_date equals current → clear override, update move_in_date, write import_row OK, applied_count++. If override and date differs → write skip audit only (no DB change to move_in_date), write import_row. If no override and old move_in_date != incoming → update move_in_date, audit, write import_row OK, applied_count++.
  - Turnovers are **not** closed by this report; only move_in_date is updated.

### AVAILABLE_UNITS

- **Parse:** CSV skip 5 rows; columns `Unit`, `Status`, `Available Date`, `Move-In Ready Date`. Normalize unit; parse Move-In Ready Date (Excel serial or string); parse Available Date; filter by phase; store raw_json for reconciliation.
- **Apply:** For each row:
  - Normalize status (e.g. vacant ready, on notice). If status allows turnover creation (vacant ready/not ready, beacon ready/not ready) and unit missing → ensure unit. If status does not allow creation and unit missing → IGNORED, conflict_reason NO_OPEN_TURNOVER_FOR_READY_DATE, continue.
  - Get open turnover. **If no open turnover:** If status allows creation and available_date missing → INVALID, AVAILABLE_DATE_MISSING. If status allows creation and available_date present → create turnover via `find_or_create_turnover_for_unit` (move_out_date = available_date), set report_ready_date, available_date, availability_status; write import_row OK, conflict_reason CREATED_TURNOVER_FROM_AVAILABILITY, applied_count++. If creation fails → CONFLICT TURNOVER_CREATION_FAILED. If status is Vacant with available_date but branch didn’t create (invariant safeguard) → INVALID VACANT_ROW_WITHOUT_TURNOVER. Else → IGNORED NO_OPEN_TURNOVER_FOR_READY_DATE.
  - **If open turnover exists:** Respect ready_manual_override_at and status_manual_override_at. If override on ready and incoming ready matches current → clear overrides, update report_ready_date, available_date, availability_status as needed, applied_count++. If override and differs → write skip audit only for ready/status. If no override → update report_ready_date, available_date, availability_status when different; audit; applied_count++ when ready changed. Always write import_row OK.
- **Lifecycle rule:** report_ready_date comes only from Move-In Ready Date; available_date from Available Date; no cross-fill.
- **After apply:** `reconcile_available_units_readiness_from_latest`: for latest batch rows, for each unit with an open turnover *now*, backfill report_ready_date, available_date, availability_status from raw_json (so previously IGNORED rows get applied once turnover exists). Then `reconcile_available_units_vacancy_invariant`: for latest batch rows with validation_status IGNORED and conflict_reason NO_OPEN_TURNOVER_FOR_READY_DATE, if raw Status is vacant and Available Date present → ensure unit, create turnover if none (via turnover_service.create_turnover_and_reconcile), update import_row to OK and CREATED_TURNOVER_FROM_AVAILABILITY, set available_date and availability_status on turnover.

### PENDING_FAS

- **Parse:** CSV skip 4 rows; rename "Unit Number" → "Unit"; columns `Unit`, `MO / Cancel Date`. Normalize unit, parse date; filter by phase.
- **Apply:** For each row:
  - Get unit by norm. If missing → IGNORED, conflict_reason NO_OPEN_TURNOVER_FOR_VALIDATION, write import_row, continue.
  - Get open turnover. If none → same IGNORED, write import_row, continue.
  - **If open turnover has no legal_confirmation_source:** Set confirmed_move_out_date = mo_cancel_date, legal_confirmation_source = "fas", legal_confirmed_at = now_iso; update turnover; audit. Compute effective_move_out_date (domain.lifecycle); call `reconcile_sla_for_turnover` with new anchor so SLA/breach is updated.
  - If legal_confirmation_source already set, no turnover update; only import_row is still written (OK).
  - Write import_row OK with move_out_date = mo_iso.

---

## 3. Business Rules (Extracted)

### MOVE_OUTS

- **Turnover creation:** When there is no open turnover for the unit, a turnover is created. Required: unit exists (created if needed), Move-Out Date present. Creation uses `turnover_service.create_turnover_and_reconcile` (insert turnover, instantiate tasks from templates, SLA reconcile, risk reconcile). Source key: `property_id:unit_norm:move_out_iso`.
- **Existing turnover:** If open turnover exists, it is updated (scheduled_move_out_date, optionally move_out_date when no legal confirmation). Duplicates (same unit in same batch) are processed per row; last write wins for that unit.
- **Open turnover with same unit:** Only one open turnover per unit; the existing one is updated.
- **Manual override:** If scheduled_move_out_date has a manual override and incoming date matches → clear override and apply. If incoming differs → do not overwrite; record skip audit; row outcome SKIPPED_OVERRIDE.
- **Legal confirmation:** When legal_confirmation_source is set, move_out_date is not overwritten by import; scheduled_move_out_date is still aligned to report.
- **Missing move-out tracking:** Open turnovers not appearing in the batch get missing_moveout_count incremented; after 2 consecutive absences they are canceled (canceled_at, cancel_reason "Move-out disappeared from report twice").
- **Phase filter:** Rows whose normalized unit code’s phase is not in VALID_PHASES (config) are dropped before apply.

### MOVE_INS (PENDING_MOVE_INS)

- **Turnovers not closed:** Move-in date only updates the open turnover’s move_in_date; no closed_at or status transition.
- **Readiness:** Readiness (report_ready_date) is not set by this report; it comes from AVAILABLE_UNITS or manual.
- **Conflict:** Move-in row for a unit with no open turnover → CONFLICT (MOVE_IN_WITHOUT_OPEN_TURNOVER). Unit is still ensured so Report Operations can resolve by creating turnover with move-out date.
- **Manual override:** If move_in_date has override and incoming matches → clear override and apply. If differs → skip overwrite, write skip audit only.

### AVAILABLE_UNITS

- **Readiness:** report_ready_date is set from Move-In Ready Date only; available_date from Available Date only; availability_status from Status. No cross-fill.
- **Tasks:** New turnovers created from this report get tasks via the same create_turnover path (turnover_service → instantiate_tasks_for_turnover).
- **Overrides:** ready_manual_override_at and status_manual_override_at are respected: match → clear and apply; differ → skip overwrite, write skip audit.
- **Vacant invariant:** Vacant status + Available Date with no open turnover must create a turnover; if that branch is not taken, an explicit INVALID (VACANT_ROW_WITHOUT_TURNOVER) is written.
- **Status semantics:** "vacant ready", "vacant not ready" (and optionally "beacon ready", "beacon not ready") allow creating a turnover when none exists; "on notice", "on notice (break)" do not.
- **Reconciliation:** After apply, readiness is backfilled from latest batch to all units that *now* have an open turnover; then vacancy invariant is run on latest batch (create turnover for previously IGNORED vacant rows, update import_row to OK).

### PENDING_FAS

- **Confirmation:** When open turnover has no legal_confirmation_source, confirmed_move_out_date is set to MO / Cancel Date, legal_confirmation_source = "fas", legal_confirmed_at = now. When already set, no change to confirmation.
- **Notes/flags:** This report does not create notes or flags; FAS Tracker notes are separate (Report Operations tab, upsert_fas_note by unit_id and fas_date).
- **SLA:** After setting confirmation, effective_move_out_date is derived (domain.lifecycle); reconcile_sla_for_turnover is called so SLA events/breach are updated for the new anchor.

---

## 4. Row Outcome Logic

| Outcome / validation_status | Meaning | When used |
|----------------------------|--------|-----------|
| **OK** | Row applied; turnover/unit updated as intended. | MOVE_OUTS/MOVE_INS/AVAILABLE_UNITS/PENDING_FAS when update or create succeeded. |
| **INVALID** | Row rejected for data reason (missing required field, invariant breach). | MOVE_OUTS: Move-Out Date missing. AVAILABLE_UNITS: Available Date missing for vacancy; VACANT_ROW_WITHOUT_TURNOVER; schema-level invalid. |
| **CONFLICT** | Business rule conflict (e.g. move-in without turnover). | MOVE_INS: MOVE_IN_WITHOUT_OPEN_TURNOVER. AVAILABLE_UNITS: TURNOVER_CREATION_FAILED. |
| **IGNORED** | Row skipped (e.g. no open turnover, unit unknown). | AVAILABLE_UNITS: NO_OPEN_TURNOVER_FOR_READY_DATE (and status doesn’t allow creation). PENDING_FAS: NO_OPEN_TURNOVER_FOR_VALIDATION (unit missing or no open turnover). |
| **SKIPPED_OVERRIDE** | Import value not written because of manual override; skip audit written. | MOVE_OUTS: manual override on scheduled_move_out_date and incoming date differs. (MOVE_INS/AVAILABLE_UNITS: same idea but row often still written as OK when only skip audit is written; legacy mixes OK vs SKIPPED_OVERRIDE by report.) |

**Conflict reasons (examples):** MOVE_OUT_DATE_MISSING, MOVE_IN_WITHOUT_OPEN_TURNOVER, NO_OPEN_TURNOVER_FOR_READY_DATE, NO_OPEN_TURNOVER_FOR_VALIDATION, TURNOVER_CREATION_FAILED, CREATED_TURNOVER_FROM_AVAILABILITY, VACANT_ROW_WITHOUT_TURNOVER, AVAILABLE_DATE_MISSING.

**Conditions (summary):**

- **OK:** Unit resolved, open turnover present (or created), and value applied (or override cleared when match).
- **INVALID:** Missing required date; or AVAILABLE_UNITS Vacant + Available Date but no turnover created (invariant).
- **CONFLICT:** Move-in without open turnover; or turnover creation failed.
- **IGNORED:** Unit missing or no open turnover and report does not create one (e.g. PENDING_FAS, or AVAILABLE_UNITS with status that doesn’t allow creation).
- **SKIPPED_OVERRIDE:** Manual override present and incoming value differs; value not written; skip audit written.

---

## 5. Database Effects (Tables and Operations)

### MOVE_OUTS

- **Tables modified:** `import_batch`, `import_row`, `turnover`, `unit` (if created), `task` (via template instantiation), `task_dependency`, `audit_log`, `sla_event` (via SLA reconcile), risk-related (via risk reconcile).
- **Operations:** Insert batch; per row insert import_row; ensure unit (resolve_unit, get/create phase/building/unit); get/create open turnover (insert_turnover, update_turnover_fields); instantiate tasks and dependencies; update_turnover_fields (scheduled_move_out_date, move_out_date when applicable, last_seen_moveout_batch_id, missing_moveout_count, move_out_manual_override_at clear); post_process: update_turnover_fields for all open turnovers (missing_moveout_count, canceled_at, cancel_reason); insert_audit_log.

### PENDING_MOVE_INS

- **Tables modified:** `import_batch`, `import_row`, `turnover`, `unit` (if created).
- **Operations:** Insert batch; per row insert import_row; ensure unit; update_turnover_fields (move_in_date, move_in_manual_override_at clear); insert_audit_log.

### AVAILABLE_UNITS

- **Tables modified:** `import_batch`, `import_row`, `turnover`, `unit` (if created), `task`, `task_dependency`, `audit_log`; reconciliation may update `import_row` (validation_status, conflict_reason, move_out_date) and `turnover`.
- **Operations:** Insert batch; per row insert import_row; ensure unit; find_or_create_turnover (or turnover_service.create_turnover_and_reconcile in vacancy reconciliation); update_turnover_fields (report_ready_date, available_date, availability_status, overrides); reconcile: read latest batch rows, update turnovers and optionally import_row; insert_audit_log; raw SQL UPDATE import_row in vacancy invariant path.

### PENDING_FAS

- **Tables modified:** `import_batch`, `import_row`, `turnover`, `audit_log`, `sla_event` (and related SLA/risk tables via reconcile_sla_for_turnover).
- **Operations:** Insert batch; per row insert import_row; update_turnover_fields (confirmed_move_out_date, legal_confirmation_source, legal_confirmed_at); reconcile_sla_for_turnover; insert_audit_log.

---

## 6. Extracted Domain Rules (Hidden / Scattered Logic)

- **Effective move-out date (lifecycle):** Priority: (1) manual override (move_out_manual_override_at + move_out_date), (2) legal confirmation (confirmed_move_out_date), (3) scheduled_move_out_date, (4) move_out_date. Used by SLA and lifecycle. **Location:** `domain/lifecycle.effective_move_out_date`. **New:** keep in `domain/`.
- **Lifecycle phase:** Derived from move_out_date, move_in_date, closed_at, canceled_at, today (NOTICE, VACANT, SMI, MOVE_IN_COMPLETE, STABILIZATION, CANCELED, CLOSED). **Location:** `domain/lifecycle.derive_lifecycle_phase`. **New:** `domain/`.
- **Task instantiation:** From active task templates by phase (or property fallback); template filter (e.g. has_carpet, has_wd_expected); dependencies between tasks. **Location:** `services/imports/tasks.instantiate_tasks_for_turnover` (used by turnover_service after insert_turnover). **New:** `services/` orchestration calling domain/repository for template resolution; task creation in repository.
- **SLA reconciliation:** Given effective move-out date and manual_ready_confirmed_at, evaluate breach state; open/close SLA events; update risk. **Location:** `services/sla_service.reconcile_sla_for_turnover`, `domain/sla_engine.evaluate_sla_state`. **New:** `domain/` for state rules, `services/` for orchestration, repository for persistence.
- **Missing move-out count and cancel:** Open turnovers not in the MOVE_OUTS batch get missing_moveout_count++; after 2, turnover is canceled. **Location:** `services/imports/move_outs.post_process_after_move_outs`. **New:** domain rule “cancel after N absences”, service applies it using repository.
- **Phase filter:** Only rows whose unit’s phase is in config allowed_phases are processed. **Location:** `services/imports/common._filter_phase`, `constants.VALID_PHASES`. **New:** domain or config; applied in service before apply.
- **Unit identity:** Normalize unit code; parse phase/building/unit; compose identity key; resolve or create unit. **Location:** `domain/unit_identity`, `services/imports/common._ensure_unit`, repository resolve_unit. **New:** `domain/` for normalize/parse/compose; repository for resolve/create.
- **Manual override semantics:** If incoming value equals current, clear override and apply; if differs, do not overwrite, write “import_skipped_due_to_manual_override” audit. **Location:** scattered in move_outs, move_ins, available_units. **New:** single domain rule; service applies it.

---

## 7. Legacy Anti-Patterns

- **UI holds workflow entry and result handling:** Admin screen builds command, calls workflow, commits, invalidates caches, and formats diagnostics. Acceptable if UI only delegates and displays; ensure no business decisions (e.g. outcome classification) in UI.
- **Parsing and business rules mixed:** Parse functions live next to apply; apply does “ensure unit”, “get open turnover”, “if override…”, “update fields” in one place. **New:** separate parsing (services/imports or dedicated parser) → DTOs; domain rules in domain; service orchestrates.
- **Direct repository and SQL in apply:** Apply modules call repository and sometimes raw `conn.execute` (e.g. UPDATE import_row in reconcile_available_units_vacancy_invariant). **New:** all persistence via repositories; no raw SQL in services/domain.
- **Duplicated override logic:** Manual override “match → clear, differ → skip” repeated in move_outs, move_ins, available_units with small variations. **New:** single domain rule + one service helper.
- **Reconciliation reading “latest batch” and re-processing:** AVAILABLE_UNITS reconciliation re-reads latest batch and re-applies logic (readiness backfill, vacancy invariant). **New:** explicit “reconciliation” service that uses repository to load batch and domain to decide updates; avoid ad-hoc SQL.
- **Config in constants:** VALID_PHASES from app settings in constants. **New:** config injected or read in service; domain receives phase set as parameter.
- **Outcome vs validation_status mapping:** Internal outcome (APPLIED, SKIPPED_OVERRIDE) mapped to validation_status (OK, SKIPPED_OVERRIDE) in validation module; CONFLICT/IGNORED/INVALID set in different places. **New:** single place that maps domain outcome → persistence status.
- **No explicit validation layer for “business” rules:** Schema validates columns/dates; “no open turnover”, “vacant must have turnover” etc. live inside apply. **New:** domain validators or rules that return outcome + reason; service calls them then persists.
- **Implicit dependency in reconciliation:** `reconcile_available_units_vacancy_invariant` in `available_units.py` calls `turnover_service.create_turnover_and_reconcile` but the module does not import `turnover_service`; this can cause NameError at runtime when that path runs. **New:** explicit imports and clear service boundaries.

---

## 8. Recommended Structure for New System

- **services/imports/**  
  - **orchestrator** (or `import_report_file`): checksum, NO_OP, call file/schema validation, parse, then report-specific apply service; run post-process/reconciliation when needed; return result dict. No business logic; only orchestration.
  - **move_outs_service:** orchestrate: parse → for each row call domain rules + turnover/task/SLA services, collect outcomes, call repository for import_row/batch; call post_process (missing move-out count/cancel).
  - **move_ins_service:** orchestrate parse, unit/turnover lookup, domain rule “apply move-in date (respect override)”, repository writes.
  - **available_units_service:** orchestrate parse, unit/turnover resolution, domain rules for status/ready/available and override; create turnover via turnover_service when needed; run readiness and vacancy reconciliation as separate steps using repositories.
  - **pending_fas_service:** orchestrate parse, unit/turnover lookup, domain rule “apply FAS confirmation when no legal source”; call SLA reconcile.
  - **common:** shared helpers that are pure or repository-only (e.g. _write_import_row, _to_iso_date, _normalize_unit using domain.unit_identity). No business branching.

- **domain/**  
  - **lifecycle:** effective_move_out_date, derive_lifecycle_phase (unchanged).
  - **unit_identity:** normalize_unit_code, parse_unit_parts, compose_identity_key.
  - **import_outcomes:** classify row outcome (APPLIED, SKIPPED_OVERRIDE, CONFLICT, IGNORED, INVALID) and conflict_reason from inputs (e.g. unit exists, open turnover exists, override state, incoming value).
  - **manual_override:** rule “should_apply_import_value(current, override_at, incoming) → (apply: bool, clear_override: bool)”.
  - **move_out_absence:** rule “cancel after N consecutive absences from report” (N=2 in legacy).
  - **sla_engine:** evaluate_sla_state (unchanged).
  - **availability_status:** which statuses allow turnover creation; vacant vs notice semantics (constants or small functions).

- **repositories/**  
  - **import_batch / import_row:** insert batch, insert row, get by batch, get latest batch/rows, get diagnostics, get missing move-out exceptions, get PENDING_FAS rows.
  - **turnover:** get_open_turnover_by_unit, list_open_turnovers_by_property, insert_turnover, update_turnover_fields (no business logic).
  - **unit:** resolve_unit, get_unit_by_norm, get_unit_by_id, update_unit_fields.
  - **task:** instantiate from templates (template selection can be domain/service; insert task/dependency in repository).
  - **audit_log:** insert (called from service with domain-provided reason).
  - **sla / risk:** as today, used by SLA and risk services.

- **UI**  
  - Only: upload file, build ApplyImportRow (report_type, file_path, property_id), call apply_import_row_workflow, commit, invalidate caches, display result and diagnostics. No parsing, no outcome logic, no direct DB.

- **Validation (pre-parse)**  
  - Keep in `imports/validation/`: file type/size/sheets; schema (columns, required fields, date/numeric format). No business rules (e.g. “must have open turnover”) here; those become domain outcome rules called from services.

---

*End of Legacy Import System Audit.*

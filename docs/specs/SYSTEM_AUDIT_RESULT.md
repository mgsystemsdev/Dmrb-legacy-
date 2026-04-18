# DMRB Canonical System Audit — Result

Audit performed per the DMRB Canonical System Audit Plan (read-only).  
Date: 2025-03-16.

---

## SYSTEM AUDIT RESULT

```
Architecture violations: 2
Schema violations: 1
Service behavior issues: 0
Domain violations: 0
UI inconsistencies: 0
Database invariant failures: 1

Overall system health: FAIL
```

---

## Details

### Architecture violations (2)

- **ui/screens/unit_detail.py** — imports `from domain import turnover_lifecycle`. Canonical rule: UI must call services only; domain must not be imported in UI.
- **ui/components/filters.py** — imports `from domain.priority_engine import PRIORITY_ORDER`, `from domain.turnover_lifecycle import PHASE_ORDER`, `from domain.readiness import READY, BLOCKED, ...`. Same rule: UI → services only.

No repository or direct SQL usage in UI (except `ui/data/backend.py` calling `ensure_database_ready()`, which is the allowed exception).

### Schema violations (1)

- **Live database** still has column `manager_confirmed_at` on table `task`. The codebase is canonical: `db/schema.sql` defines `task` without that column, `db/migrations/008_drop_manager_confirmed_at.sql` drops it, and `db/repository/task_repository.py` `update()` does not allow `manager_confirmed_at`. However, `ensure_database_ready()` in `db/connection.py` does **not** apply migration 008, so existing databases created from an older schema still have the column. To resolve: run migration 008 manually against the database, or add 008 to the bootstrap logic in `ensure_database_ready()`.

### Service behavior issues (0)

- **task_service.instantiate_templates** — Creates tasks from templates; skips duplicate task types via `existing_types`. No `confirm_task` or `manager_confirmed_at`.
- **turnover_service.create_turnover** — Calls `task_service.instantiate_templates` when `phase_id` exists and templates exist; otherwise writes audit "skipped: unit has no phase" or "skipped: no task templates for phase".
- **turnover_service.ensure_turnover_has_tasks** — Checks task count, calls `instantiate_templates` when zero, writes audit "Pipeline tasks generated automatically." Unit service calls it on detail load.
- **turnover_service.backfill_tasks_for_property** / **backfill_tasks_all_properties** — Layer 3: scan all open turnovers, call `ensure_turnover_has_tasks` for each (no-op when tasks exist). Used by `scripts/backfill_turnover_tasks.py` for periodic system-integrity repair.
- **turnover_service.cancel_turnover** — Sets `canceled_at` via `update_turnover`; audit trail via update path.

### Domain violations (0)

- **domain/readiness.py**, **domain/sla.py**, **domain/priority_engine.py**, **domain/import_outcomes.py** — No `db` or `repository` or `services` imports; pure computation. Priority levels include NORMAL, INSPECTION_DELAY, SLA_RISK, MOVE_IN_DANGER, LOW.

### UI inconsistencies (0)

- Task columns present on Unit Detail: Task, Assignee, Date, Execution, Completed At, Req, Blocking. Completed At maps to `vendor_completed_at`.
- No Confirm column, Confirm button, or `manager_confirmed_at` / `confirm_task` in UI. `qc_label()` in `ui/helpers/formatting.py` uses only `execution_status`.

### Database invariant failures (1)

- **All open turnovers must have tasks** — Query returned **97** rows (97 open turnovers with zero tasks).  
  Invariant: every open turnover should have at least one task (either created at turnover creation or via `ensure_turnover_has_tasks` on load). Current data has 97 open turnovers without tasks; this may be legacy data created before auto-creation/repair, or units without phase/templates. **Layer 3 (backfill) is implemented:** run the batch job `scripts/backfill_turnover_tasks.py` (or call `turnover_service.backfill_tasks_all_properties()` / `backfill_tasks_for_property(property_id)`). Schedule via cron (e.g. daily) with `DATABASE_URL` set; see [FULL_REGRESSION_AUDIT_FOLLOWUPS.md](FULL_REGRESSION_AUDIT_FOLLOWUPS.md). Alternatively ensure unit detail is opened for those units (self-heal) or accept historical exceptions and document.

Other invariant queries returned 0 rows:

- Only one open turnover per unit: 0 rows
- One task per type per turnover: 0 rows
- Completed tasks have `vendor_completed_at`: 0 rows
- No orphan tasks: 0 rows
- Import row has outcome (`validation_status` not null): 0 rows

### Pre-validation (Part 1)

- Database connected successfully.
- Counts: task_template 63, turnover 104, task 48 (all > 0).
- `turnover_repository.get_open_by_property` and `get_open_by_unit` use `AND canceled_at IS NULL`.

### Test coverage (Part 9)

- Tests exist for task_service, readiness, priority, lifecycle, sla.
- No tests reference `manager_confirmed_at` or `confirm_task`.

---

## PASS criteria (from plan)

- All invariants pass (0 rows where required) — **Not met** (97 open turnovers without tasks).
- No P1/P2-level issues — **Not met** (schema violation: live DB has deprecated column; data invariant failure).
- Only known minor architecture violation or P3 — **Not met** (2 architecture violations; 1 schema; 1 invariant).

**Overall system health: FAIL.** Address schema (apply migration 008), data (repair or document 97 open turnovers without tasks), and optionally reduce UI–domain coupling (expose lifecycle/readiness/priority via services) to achieve PASS.

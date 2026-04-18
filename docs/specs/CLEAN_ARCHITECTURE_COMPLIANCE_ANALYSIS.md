# Clean Monolith / Clean Architecture Compliance Analysis

Date: 2025-03-16  
Scope: Dependency rule, layer responsibilities, data flow, invariants/schema.

---

## 1. Dependency rule

### 1.1 UI → domain or db

**Rule:** Modules under `ui/` should only import from `services/` and `ui.*`.

| Module | Imports from `domain/` or `db/` | Compliant? |
|--------|-----------------------------------|------------|
| `ui/data/backend.py` | `from db.connection import ensure_database_ready` | **Allowed exception** (bootstrap; docs treat this as the one permitted db touch from UI). |
| All other `ui/**/*.py` | None | Yes. No `domain` or `db` imports. |

**Conclusion:** Compliant. Filter options (priority order, phase order, readiness states) are obtained via `board_service.get_board_filter_options()`; the UI does not import `domain.priority_engine`, `domain.turnover_lifecycle`, or `domain.readiness`. The violations previously reported in SYSTEM_AUDIT_RESULT (unit_detail.py and filters.py importing domain) are **no longer present** in the current codebase.

### 1.2 Domain → db, repository, or services

**Rule:** Domain should have zero imports from `db/`, `repository`, or `services/`.

| Check | Result |
|-------|--------|
| Grep `from (db\|repository\|services)` in `domain/` | No matches. |
| Domain imports | Only `domain.*` (e.g. readiness, sla, turnover_lifecycle) and stdlib (`datetime`, `re`). |

**Conclusion:** Compliant. No domain file imports db, repository, or services.

### 1.3 Services → inward only (domain, db.repository; optionally other services); never ui

**Rule:** Services may depend on `domain/`, `db.repository`, and other services; never on `ui/`.

| Check | Result |
|-------|--------|
| Grep `from ui` in `services/` | No matches. |
| Service imports | All services use `db.repository`, `domain`, and/or other `services` only. |

**Conclusion:** Compliant. No service imports UI.

---

## 2. Layer responsibilities

### 2.1 Domain: pure business rules only (no I/O, no framework)

**Checked:** All files under `domain/` (readiness, sla, priority_engine, turnover_lifecycle, import_outcomes, availability_status, unit_identity, move_out_absence, manual_override).

- **No DB, HTTP, or Streamlit.** Domain uses only `datetime`, `re`, and other `domain.*` modules.
- **No I/O.** All functions operate on dicts/dates and return computed values.

**Conclusion:** No domain file does DB, HTTP, or Streamlit. Domain is pure.

### 2.2 Services: orchestration and use-case behavior; call repositories and domain

**Checked:** board_service, turnover_service, task_service, unit_service, risk_service, import_service, etc.

- **Orchestration:** Services load data via repositories, call domain for lifecycle/readiness/SLA/priority, and return DTOs. No service was found to embed presentation logic or directly render Streamlit widgets.
- **Presentation:** Filter options and board payloads are returned as data (e.g. `get_board_filter_options()`, `get_board()`, `get_unit_detail()`); UI does the rendering.

**Conclusion:** No service embeds presentation logic or directly renders. Services orchestrate and call domain/repositories.

### 2.3 Repositories: raw data access only (parameterized SQL)

**Checked:** task_repository, turnover_repository, unit_repository, and other `db/repository/*.py`.

- **Pattern:** All use `get_connection()`, parameterized SQL (`%s`), and return dicts/lists. No workflow or business rules (only trivial `if not fields` / allowlists for updates).
- **task_repository.update():** Allows only schema-backed fields (`scheduled_date`, `vendor_due_date`, `execution_status`, `vendor_completed_at`, `completed_date`, `required`, `blocking`, `assignee`). No `manager_confirmed_at`.

**Conclusion:** Repositories contain no workflow or business rules; only raw data access.

### 2.4 UI: rendering and calling services only

**Checked:** ui/screens/*.py, ui/components/*.py, ui/helpers/formatting.py.

- **No business rules:** UI does not implement lifecycle, readiness, or priority logic; it displays data returned by services.
- **No SQL or repository usage:** No `repository` or raw SQL in UI (except `ui/data/backend.py` → `db.connection.ensure_database_ready`, which is the documented exception).
- **Exception — presentation logic that references removed schema:**  
  **`ui/helpers/formatting.py`** — `qc_label()` (lines 154–161) uses `manager_confirmed_at` to decide “Confirmed” vs “Pending”. The column was removed in migration 008; completion is now solely `execution_status = 'COMPLETED'` and `vendor_completed_at`. So this is **stale logic**: it references a deprecated column and will always show “Pending” on current schema (or wrong behavior if a DB still has the column). **Recommendation:** Change `qc_label()` to derive QC status from `execution_status` and `vendor_completed_at` (and optionally `completed_date`) only; remove any dependency on `manager_confirmed_at`.

**Conclusion:** UI is otherwise presentation-only. The only violation is `qc_label()` depending on deprecated `manager_confirmed_at`.

---

## 3. Data flow (derived vs persisted)

**Intended (architecture_rules.md, canonical_data_model.md):**

- **Computed (not stored):** lifecycle phase, readiness state, DV/DTBR, board priority, risk-radar scores, board summary metrics.
- **Persisted:** Turnover dates and overrides, tasks and confirmations, notes, risk flags and SLA events, import batches/rows, audit events.

**Implementation:**

- **Lifecycle phase:** Computed in `domain.turnover_lifecycle.lifecycle_phase()`; used by board_service and unit_service. Not stored.
- **Readiness:** Computed in `domain.readiness.readiness_state()` (and related) from tasks; used by board_service and task_service. Not stored.
- **DV / DTBR:** Computed in domain (e.g. `days_since_move_out`, `days_to_be_ready`); attached to payloads by services. Not stored.
- **Priority:** Computed in `domain.priority_engine`; used by board_service. Not stored.
- **Risk / SLA:** Computed in domain/sla and risk_service; not stored as derived fields (sla_event table stores breach events as facts).
- **Task completion:** Stored facts are `execution_status`, `vendor_completed_at`, `completed_date`. No stored “manager_confirmed_at” in current schema.

**Conclusion:** Derived values are computed in domain/service; only stored facts are persisted. No stored fields that should be derived were identified. The only mismatch is UI’s `qc_label()` still treating the removed `manager_confirmed_at` as the source of “Confirmed” status.

---

## 4. Summary

The codebase **behaves like a clean monolith**: layers are separated, the dependency rule is respected (UI → services only except the allowed `db.connection` in backend; domain has no db/repository/services imports; services never import UI), and the domain is pure while services orchestrate and repositories do raw data access. Derived values (lifecycle, readiness, DV/DTBR, priority, risk) are computed in domain/service and not stored.

**Top 3 violations or gaps:**

1. **`ui/helpers/formatting.py` — `qc_label()`**  
   Still uses `manager_confirmed_at`, which was dropped in migration 008. QC status should be derived only from `execution_status`, `vendor_completed_at`, and optionally `completed_date`.

2. **Schema/bootstrap vs live DB (if migration 008 was not applied)**  
   `db/schema.sql` and `db/repository/task_repository.py` are aligned with the canonical model (no `manager_confirmed_at`; `completed_date` present). `db/connection.py` applies migration 008 when `manager_confirmed_at` exists. If a live database was created from an older schema and 008 was never run, that DB would still have the column; running 008 (or relying on `ensure_database_ready()` to apply it) resolves the schema violation.

3. **Documentation gap**  
   `docs/specs/canonical_data_model.md` “Task” key fields do not list `completed_date`. The schema and migrations include it; the doc should be updated for accuracy.

---

## 5. Invariants and schema

### 5.1 Intended DB invariants (from docs)

From **SYSTEM_AUDIT_RESULT.md**, **canonical_data_model.md**, and **architecture_rules.md**:

| Invariant | Enforcement | Code/migrations |
|-----------|-------------|------------------|
| Only one open turnover per unit | Unique partial index `ux_turnover_one_open` on `(unit_id)` WHERE `closed_at IS NULL AND canceled_at IS NULL` | In `db/schema.sql`. |
| One task per type per turnover | Unique constraint `task_turnover_task_type_unique` on `(turnover_id, task_type)` | In `db/schema.sql`. |
| Completed tasks have `vendor_completed_at` | CHECK `task_completed_requires_vendor_completed_at` | In `db/schema.sql`. |
| No orphan tasks | FK `task_turnover_fk` to turnover | In `db/schema.sql`. |
| Import row has outcome | `validation_status` NOT NULL; CHECK for allowed values | In `db/schema.sql`. |
| All open turnovers have tasks | **Not** enforced by schema; enforced by application (create + ensure_turnover_has_tasks + backfill) | No DB constraint. SYSTEM_AUDIT_RESULT notes 97 open turnovers with zero tasks as a data invariant failure; backfill script exists. |
| Task table has no `manager_confirmed_at` | Dropped by migration 008 | `008_drop_manager_confirmed_at.sql`; `ensure_database_ready()` applies it when column exists. |
| Task has `completed_date` | Added by migration 009 | `009_add_task_completed_date.sql`; `ensure_database_ready()` applies it when column missing. |

### 5.2 Code and migrations vs schema

| Item | Status |
|------|--------|
| **db/schema.sql** | Defines `task` without `manager_confirmed_at`, with `completed_date`. Matches intended canonical model. |
| **db/migrations/** | 001–009 present; 008 drops `manager_confirmed_at`; 009 adds `completed_date`. |
| **db/connection.py** | Applies 005, 006, 007, **008**, **009** when relevant (e.g. 008 if `manager_confirmed_at` exists; 009 if `completed_date` missing). So bootstrap **does** apply 008 and 009. |
| **db/repository/task_repository.py** | `update()` allowlist omits `manager_confirmed_at` and includes `completed_date`. Aligned with schema. |
| **App expectation** | No code path writes or reads `manager_confirmed_at` except **ui/helpers/formatting.py** `qc_label()`, which still reads it for display. That one place is the mismatch. |

### 5.3 Mismatches and deprecated usage

- **Deprecated column still in use (UI only):**  
  **`ui/helpers/formatting.py`** uses `manager_confirmed_at` in `qc_label()`. Column is removed in schema and migrations; repository does not expose or update it. Fix: derive QC label from `execution_status` and `vendor_completed_at` (and optionally `completed_date`) only.

- **canonical_data_model.md:**  
  Task “Key fields” should include `completed_date` for consistency with schema and migrations.

- **Live DBs created before 008/009 in bootstrap:**  
  Any existing database that had `manager_confirmed_at` will have it dropped when `ensure_database_ready()` runs (008). New DBs from schema.sql never have it. So after one run of bootstrap, schema and code (except `qc_label()`) are aligned.

---

## References

- `docs/specs/SYSTEM_AUDIT_RESULT.md`
- `docs/specs/architecture_rules.md`
- `docs/specs/canonical_data_model.md`
- `db/schema.sql`, `db/connection.py`, `db/migrations/`
- `ui/helpers/formatting.py` (qc_label)
- `services/board_service.py` (get_board_filter_options, get_board)

# Confirm Field — System Trace and Impact Analysis

**Objective:** Determine whether the Confirm column is necessary or if task completion can be determined solely by Execution status and date.  
**Scope:** Full DMRB system (database, services, UI, operational logic).  
**Date:** 2025-03-16.  
**No code changes were made; this is analysis only.**

---

## Step 1 — Database Schema

### Task table: Confirm-related storage

- **Column name:** `manager_confirmed_at` (there is no column literally named "Confirm").
- **Column type:** `TIMESTAMPTZ` (nullable).
- **Confirmed timestamp:** Yes. The confirmation state is represented by the timestamp `manager_confirmed_at` (set when a manager confirms; NULL = not confirmed).

### Full `task` table structure (from `db/schema.sql`)

| Column               | Type         | Constraints / Notes |
|----------------------|-------------|----------------------|
| task_id              | BIGINT      | PK, identity         |
| property_id          | BIGINT      | NOT NULL, FK → property |
| turnover_id          | BIGINT      | NOT NULL, FK → turnover |
| task_type            | TEXT        | NOT NULL, not blank   |
| scheduled_date       | DATE        | nullable              |
| vendor_due_date      | DATE        | nullable              |
| execution_status     | TEXT        | NOT NULL, default 'NOT_STARTED'; CHECK IN ('NOT_STARTED','SCHEDULED','IN_PROGRESS','COMPLETED') |
| vendor_completed_at  | TIMESTAMPTZ | nullable              |
| **manager_confirmed_at** | **TIMESTAMPTZ** | **nullable** |
| required             | BOOLEAN     | NOT NULL, default TRUE |
| blocking             | BOOLEAN     | NOT NULL, default TRUE |
| assignee             | TEXT        | nullable              |
| created_at           | TIMESTAMPTZ | NOT NULL, default NOW() |
| updated_at           | TIMESTAMPTZ | NOT NULL, default NOW() |

**Constraints relevant to Confirm:**

- `task_completed_requires_vendor_completed_at`: if `execution_status = 'COMPLETED'` then `vendor_completed_at` must be non-NULL.
- `task_manager_confirmed_requires_completion`: if `manager_confirmed_at` is non-NULL then `execution_status` must be `'COMPLETED'`.

So: confirmation is stored only as `manager_confirmed_at`; there is no separate "confirmation_status" enum column. The same structure appears in `db/migrations/001_initial.sql`.

---

## Step 2 — Service Layer Usage

### Where Confirm is read

| Location | Usage |
|----------|--------|
| `db/repository/task_repository.py` | `update()` allows `manager_confirmed_at` in allowed fields; `get_by_turnover()` / `get_by_id()` return full row (including `manager_confirmed_at`) via `SELECT *`. |
| `domain/readiness.py` | `confirmed_count(tasks)` returns `(manager_confirmed_count, completed_count)` using `manager_confirmed_at`. |
| `services/task_service.py` | `confirm_task()` reads `execution_status` to enforce "must be COMPLETED before confirmation". |

### Where Confirm is written

| Location | Function | Behavior |
|----------|----------|----------|
| `services/task_service.py` | `confirm_task(task_id, actor)` | Sets `manager_confirmed_at=datetime.utcnow()` via `update_task()`. Fails if task not COMPLETED. |

There is no service that clears `manager_confirmed_at` or sets "Rejected"/"Waived"; the only write is "set timestamp on confirm."

### Where Confirm is used in logic

| Service / module | Function | How Confirm affects behavior |
|------------------|----------|------------------------------|
| **task_service** | `confirm_task` | Only allows setting `manager_confirmed_at` when `execution_status == 'COMPLETED'`. |
| **readiness** | `readiness_state`, `blocking_tasks`, `completion_ratio`, `next_pending_task` | **Do not use** `manager_confirmed_at`. They use only `execution_status` (e.g. COMPLETED). |
| **readiness** | `confirmed_count` | Uses `manager_confirmed_at` to count confirmed vs completed. **Not used by any production code** — only by `tests/domain/test_readiness.py`. |
| **turnover_service** | — | No references to `manager_confirmed_at` or confirmation. |
| **board_service** | `get_board`, metrics, flags | Does **not** use `manager_confirmed_at`. Uses `readiness_domain.readiness_state`, `completion_ratio`, `blocking_tasks` (all execution-based). |
| **QC logic** | — | QC status is derived in UI helper `qc_label(tasks)` (see Step 3 / 4). |
| **Risk / SLA** | `domain/priority_engine.py`, `domain/sla.py` | Priority and SLA use only `readiness_state(tasks)` and turnover/dates; **no** use of `manager_confirmed_at`. |

**Exact functions where Confirm affects behavior:**

- **task_service:** `confirm_task()` — only place that writes `manager_confirmed_at`.
- **readiness:** `confirmed_count()` — reads `manager_confirmed_at` (used only in tests).
- **UI/formatting:** `qc_label()` in `ui/helpers/formatting.py` — uses `manager_confirmed_at` to compute QC "Confirmed" vs "Pending" (see Steps 3–4).

---

## Step 3 — UI Usage

### Where Confirm is displayed

| Screen / component | How Confirm is shown |
|--------------------|------------------------|
| **Unit Detail** (`ui/screens/unit_detail.py`) | Tasks table has a **Confirm** column; shows "Confirmed" if `manager_confirmed_at` is set, else "Pending". QC panel shows `qc_label(tasks)` and a "✅ Confirm Quality Control" button when there are completed-but-unconfirmed tasks. |
| **Board / Board table** (`ui/screens/board.py`, `ui/components/board_table.py`) | QC column shows `qc_label(tasks)` ("Confirmed" vs "Pending"). Board filter includes "QC Done" / "QC Not Done" based on `qc_label(...) == "Confirmed"`. No per-task Confirm column on the board. |
| **Property Structure** (`ui/screens/property_structure.py`) | Unit/turnover table has a "QC" column: `qc_label(tasks)` (aggregate Confirm state). |
| **Task panel** (`ui/components/task_panel.py`) | Per task: shows a "Confirm" button when task is completed but not confirmed (`manager_confirmed_at` is None). |
| **Admin** (`ui/screens/admin.py`) | Lists "Confirmation Statuses" in a read-only list (CONFIRM_LABELS: Pending, Confirmed, Rejected, Waived). No read/write of `manager_confirmed_at`. |

### Where Confirm can be modified

| Location | Control | Action |
|----------|---------|--------|
| **Unit Detail** | Tasks table — **Confirm** selectbox (per task) | Options: CONFIRM_LABELS ("Pending", "Confirmed", "Rejected", "Waived"). Disabled when task is not completed. On Save: if user selects "Confirmed" and task was not confirmed, calls `task_service.confirm_task(tid, actor="manager")`. "Rejected" and "Waived" have no persist path (no backend to clear or set state). |
| **Unit Detail** | "✅ Confirm Quality Control" button | Confirms all completed tasks that have `manager_confirmed_at` is None for that turnover. |
| **Task panel** | "Confirm" button per task | Calls `task_service.confirm_task(task_id, actor="manager")` when task is completed and not confirmed. |

**Operations Schedule** (`ui/screens/operations_schedule.py`): Does **not** display or edit Confirm; only shows task type, unit, date, assignee, and execution Status. `task_service.get_schedule_rows()` does not include `manager_confirmed_at`.

Summary: Confirm is displayed and modified on **Unit Detail** (table + QC button) and in the **Task panel**; it drives the **QC** column and filter on **Board** and **Property Structure**. It is not shown or edited on Operations Schedule.

---

## Step 4 — Operational Logic Impact

### Readiness state

- **Readiness** (`domain/readiness.py`: `readiness_state`, `blocking_tasks`, `completion_ratio`, `next_pending_task`) uses only `execution_status == 'COMPLETED'`.
- **Confirm does not affect readiness.** A unit can be READY with all blocking tasks COMPLETED even if none are manager-confirmed.

### QC completion

- **QC status** is defined in `ui/helpers/formatting.py`: `qc_label(tasks)`:
  - "Confirmed" only when **all** completed tasks have `manager_confirmed_at` set.
  - Otherwise "Pending".
- So **Confirm directly drives QC completion** in the UI and in the board QC filter ("QC Done" / "QC Not Done").

### Board status

- Board priority and status use **readiness** (execution-based) and SLA/date logic. **Confirm does not affect board priority or board status.**
- The only board impact of Confirm is the **QC** column and the **QC filter** (filter by QC Done / QC Not Done).

### SLA calculations

- SLA logic (`domain/sla.py`) uses turnover dates and thresholds only. **Confirm is not used.**

### Risk scoring

- Priority/risk (`domain/priority_engine.py`) uses `readiness_state(tasks)` and turnover/dates. **Confirm is not used.**

### Reports or exports

- **Export Reports** (`ui/screens/export_reports.py`): Placeholder buttons only; no task or Confirm data exported.
- No other report or export found that includes `manager_confirmed_at` or confirmation status.

**Summary:** Confirm affects **only** the **QC** concept: QC label ("Confirmed" vs "Pending") and the board QC filter. It does **not** affect readiness, board priority, SLA, risk, or any current reports/exports.

---

## Step 5 — Execution vs Confirm Relationship

### Current lifecycle

1. **Creation** — Task created with `execution_status = 'NOT_STARTED'`, `vendor_completed_at` and `manager_confirmed_at` NULL.
2. **Execution** — Status can move to SCHEDULED, IN_PROGRESS, then COMPLETED. When set to COMPLETED (via `complete_task()` or equivalent update), **vendor_completed_at** is set to `datetime.utcnow()`.
3. **Confirm** — After COMPLETED, a manager may call `confirm_task()`, which sets **manager_confirmed_at** to `datetime.utcnow()`. It is a separate, optional step.

So:

- **Execution = Completed** means: `execution_status == 'COMPLETED'` and `vendor_completed_at` is set (enforced by DB and `complete_task()`).
- **Confirm = Confirmed** means: `manager_confirmed_at` is not NULL (and by constraint, execution must already be COMPLETED).

They are **different stages**: completion is "work done" (execution + vendor_completed_at); confirmation is "manager approved" (manager_confirmed_at). The system does **not** treat "task done" as identical to "task confirmed"; QC is explicitly "all completed tasks confirmed."

### Timestamps

- **vendor_completed_at** — Set when execution becomes COMPLETED (completion timestamp).
- **manager_confirmed_at** — Set when manager confirms (confirmation timestamp).

So task completion can already be determined by **Execution status + vendor_completed_at**; Confirm adds a second, optional step and a second timestamp.

---

## Step 6 — Removal Feasibility

### Could the system rely only on Execution status and execution completion timestamp?

Yes. Operationally:

- Readiness, board priority, SLA, and risk already depend only on execution (and dates).
- The only behavioral dependency on Confirm is **QC**: today "QC Done" means "all completed tasks have manager_confirmed_at set." If Confirm were removed, QC could be redefined to mean "all required/blocking tasks are COMPLETED" (and optionally use `vendor_completed_at` as the completion timestamp). That would align "QC Done" with "execution complete" and remove the need for a separate confirmation step.

### If Confirm were removed — what would need to change

**Database**

- `db/schema.sql`, `db/migrations/001_initial.sql`: Drop column `manager_confirmed_at` and constraint `task_manager_confirmed_requires_completion`. A new migration would be required for existing DBs.

**Repository**

- `db/repository/task_repository.py`: Remove `manager_confirmed_at` from the `allowed` set in `update()`.

**Services**

- `services/task_service.py`: Remove `confirm_task()`; optionally in `complete_task()` (or wherever COMPLETED is set) ensure `vendor_completed_at` is set so completion timestamp is always present for COMPLETED tasks.

**Domain**

- `domain/readiness.py`: Remove or repurpose `confirmed_count()` (currently only used in tests).

**UI**

- `ui/helpers/formatting.py`: Change `qc_label(tasks)` to derive QC from execution only (e.g. "Confirmed" when all completed per execution_status, or remove QC label if no longer needed).
- `ui/screens/unit_detail.py`: Remove Confirm column, CONFIRM_LABELS usage, "Confirm Quality Control" button, and confirmation handling in `_save_task_changes()`.
- `ui/screens/board.py`: Update QC filter to use the new QC definition (execution-only).
- `ui/components/task_panel.py`: Remove "Confirm" button and any logic that checks `manager_confirmed_at`.
- `ui/screens/property_structure.py`: No change if QC column stays and is redefined to execution-only.
- `ui/screens/admin.py`: Remove or adjust "Confirmation Statuses" read-only list.
- `ui/state/constants.py`: Remove or reduce `CONFIRM_LABELS` if unused.

**Tests**

- `tests/services/test_task_service.py`: Remove tests for `confirm_task` and `confirm_incomplete_raises`.
- `tests/domain/test_readiness.py`: Remove or adjust `TestConfirmedCount` and any tests that rely on `manager_confirmed_at`.
- `tests/domain/test_priority.py`: Remove `manager_confirmed_at` from task fixtures if present.

**Docs**

- `docs/specs/canonical_data_model.md`: Remove or update `manager_confirmed_at` from the task model.

### Logic that would break if removed without replacement

- **QC meaning:** Any process or user that interprets "QC Done" as "manager has confirmed all completed tasks" would see a behavior change; if QC is redefined to "all blocking tasks COMPLETED," behavior becomes consistent with execution-only.
- **Confirm button / Confirm column:** Would be removed; no replacement needed if completion is considered final at COMPLETED + vendor_completed_at.
- **confirmed_count:** Only used in tests; removal or test update is sufficient.

No other operational logic (readiness, board priority, SLA, risk, reports) depends on Confirm.

---

## Step 7 — Recommendation

### Option A — Keep Confirm

- **When to choose:** If the business requires a distinct "manager confirmation" step after execution (e.g. audit, accountability, or "work done vs approved").
- **Impact:** No change; current behavior and QC definition remain.

### Option B — Remove Confirm and simplify

- **Simplified lifecycle:** Execution → Completed (with `vendor_completed_at` set when status becomes COMPLETED). No separate Confirm step.
- **QC:** Define QC as "all required/blocking tasks COMPLETED" (and optionally use `vendor_completed_at` as the completion timestamp).
- **Safer from a system perspective:** Fewer columns, one less state to keep in sync, no "Rejected"/"Waived" labels that are not persisted. Readiness, priority, SLA, and risk already ignore Confirm; only QC and UI need to be aligned with the new definition.
- **Risk:** Process/contractual need for an explicit "manager confirmed" moment would be lost unless reimplemented elsewhere (e.g. a separate approval workflow or audit log).

### Final recommendation

- **If there is no business or compliance need for a separate "manager confirmation" after completion:** **Option B (remove Confirm)** is technically safe and simplifies the model. Completion would be determined solely by Execution status and `vendor_completed_at`; QC would mean "execution complete" for the unit.
- **If manager confirmation is required for accountability or audits:** **Option A (keep Confirm)** is appropriate; the current design supports that distinction (Execution = completed, Confirm = manager approved).

The trace shows that **Confirm has limited operational impact** (QC label and QC filter only) and that **removal is feasible** with a bounded set of file and logic changes, provided QC is redefined to execution-only and the above UI/repo/service/test/doc updates are applied.

---

## Summary Tables

### Database usage

| Item | Detail |
|------|--------|
| Column | `manager_confirmed_at` (TIMESTAMPTZ, nullable) |
| Constraint | `manager_confirmed_at` non-NULL ⇒ `execution_status = 'COMPLETED'` |
| Other timestamp | `vendor_completed_at` (set when execution becomes COMPLETED) |

### Service usage

| Service / module | Read | Write | Logic |
|------------------|------|-------|--------|
| task_service | — | `confirm_task()` sets `manager_confirmed_at` | Enforces COMPLETED before confirm |
| task_repository | SELECT returns column; update allows it | update() | — |
| readiness | `confirmed_count()` | — | Only `confirmed_count` uses it; unused in prod |
| board_service | — | — | No |
| turnover_service | — | — | No |
| SLA / priority | — | — | No |

### UI usage

| Place | Display | Modify |
|-------|---------|--------|
| Unit Detail | Confirm column; QC panel + button | Confirm selectbox; "Confirm Quality Control" button |
| Board / board_table | QC column; QC filter | — |
| Property Structure | QC column | — |
| Task panel | — | "Confirm" button |
| Admin | Confirmation Statuses list (read-only) | — |
| Operations Schedule | — | — |

### Operational dependencies

| Area | Uses Confirm? |
|------|----------------|
| Readiness state | No |
| QC completion | Yes (qc_label) |
| Board status / priority | No |
| SLA calculations | No |
| Risk scoring | No |
| Reports / exports | No |

### Removal impact (files to change)

| Layer | Files |
|-------|--------|
| DB | `db/schema.sql`, `db/migrations/001_initial.sql` + new migration |
| Repository | `db/repository/task_repository.py` |
| Services | `services/task_service.py` |
| Domain | `domain/readiness.py` |
| UI | `ui/helpers/formatting.py`, `ui/screens/unit_detail.py`, `ui/screens/board.py`, `ui/components/task_panel.py`, `ui/screens/admin.py`, `ui/state/constants.py`; optionally `ui/screens/property_structure.py` |
| Tests | `tests/services/test_task_service.py`, `tests/domain/test_readiness.py`, `tests/domain/test_priority.py` |
| Docs | `docs/specs/canonical_data_model.md` |

---

*End of report. No code was modified.*

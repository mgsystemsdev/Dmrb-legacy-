# DMRB Full Regression Audit Report

Read-only diagnostic audit. No code changes.

Date: 2026-03-16.

---

## Step 1 — Database Verification

**Task table schema**

- [db/schema.sql](../db/schema.sql): `task` includes `completed_date DATE` (line 169). No `manager_confirmed_at`, no `task_manager_confirmed_requires_completion`.
- [db/migrations/008_drop_manager_confirmed_at.sql](../db/migrations/008_drop_manager_confirmed_at.sql): Drops constraint `task_manager_confirmed_requires_completion` and column `manager_confirmed_at`.
- [db/migrations/009_add_task_completed_date.sql](../db/migrations/009_add_task_completed_date.sql): Adds `completed_date DATE` with `IF NOT EXISTS`.

**Migrations 008 and 009 at bootstrap**

- [db/connection.py](../db/connection.py) `ensure_database_ready()` (lines 90–120):
  - **008**: Applied if `task` has column `manager_confirmed_at` (checks `information_schema.columns`); then runs 008 SQL (drops constraint and column).
  - **009**: Applied if `task` does **not** have column `completed_date`; then runs 009 SQL (adds column).

**Result:** Database layer is correct. Schema and migrations match refactor intent; 008 and 009 are applied during bootstrap. Note: [SYSTEM_AUDIT_RESULT.md](SYSTEM_AUDIT_RESULT.md) previously reported that 008 was not applied; current `db/connection.py` **does** apply both 008 and 009.

---

## Step 2 — Task Lifecycle

**Flow: UI → task_service → repository → database**

| Layer          | Evidence |
| -------------- | -------- |
| **UI**         | [ui/screens/unit_detail.py](../ui/screens/unit_detail.py), [ui/screens/operations_schedule.py](../ui/screens/operations_schedule.py), [ui/components/task_panel.py](../ui/components/task_panel.py): Only set `execution_status` (and related fields). Never send `completed_date`. Complete action calls `task_service.complete_task()` → `update_task(..., execution_status="COMPLETED", vendor_completed_at=...)`. |
| **Service**    | [services/task_service.py](../services/task_service.py) (lines 79–85): When `execution_status` becomes `COMPLETED`, and caller did not pass `completed_date`, and existing task has no `completed_date`, service sets `fields["completed_date"] = date.today()`. Never overwrites existing `completed_date`. |
| **Repository** | [db/repository/task_repository.py](../db/repository/task_repository.py): `update()` allows `completed_date` in `allowed`; writes it via generic `UPDATE task SET ...`. |
| **Database**   | Column `task.completed_date`; no trigger; idempotency enforced in service. |

**Scenarios**

- **Task marked completed:** Service stamps `completed_date` on first transition to COMPLETED.
- **Task edited after completion:** Service does not add `completed_date` (existing already set); preserved ([tests/services/test_task_service.py](../tests/services/test_task_service.py) `test_completed_date_unchanged_when_editing_after_completion`).
- **Task reopened:** `completed_date` left as-is ([tests/services/test_task_service.py](../tests/services/test_task_service.py) `test_completed_date_preserved_when_task_reopened`).

**Result:** No layer bypass. UI only changes execution status; service stamps `completed_date` once; repository allows updates; write-once behavior is correct.

---

## Step 3 — Flag Bridge Evaluation Pipeline

**Order of execution** ([services/board_service.py](../services/board_service.py) `get_board()`)

1. **Guard rails** — `_evaluation_gate(turnover, today)` (line 251). If `"skip_evaluation"` or `"vacant_ready"` → `_build_healthy_board_item(...)`, no agreement evaluation.
2. **Agreement evaluation** — `evaluate_turnover_agreements(turnover, tasks, today, ...)` (lines 274–276).
3. **Priority derivation** — `derive_priority_from_agreements(agreements)` (line 277), then `urgency_sort_key(priority, turnover, today)`.
4. **Board rendering** — Flag Bridge loads via `board_service.get_board_view()` and renders breach table from board items.

**Independence of flags and priority**

- Priority is derived **from** agreements ([domain/priority_engine.py](../domain/priority_engine.py) `derive_priority_from_agreements`). Docstring: "Priority is a summary for sorting and display; it does not modify agreements."
- Flags (inspection, sla, move_in, plan, viol) are set independently in `evaluate_turnover_agreements()`; multiple red allowed (e.g. [tests/services/test_board_service.py](../tests/services/test_board_service.py) `test_evaluate_turnover_agreements_multiple_red_flags`).

**Agreement rules** (all in `evaluate_turnover_agreements()`, [services/board_service.py](../services/board_service.py) 46–124)

- **Inspection:** INSPECTION task types; days since move-out and blockers → RED / YELLOW / GREEN.
- **SLA:** `days_out > AGREEMENT_SLA_DAYS` (10) and readiness ≠ READY → RED.
- **Move-in:** `move_in_date` set, `days_in ≤ 3`, readiness ≠ READY → RED.
- **Plan:** `report_ready_date` set, `today > report_ready_date`, readiness ≠ READY → RED.
- **Viol:** `"RED" if (sla_flag == "RED" or move_in_flag == "RED") else "GREEN"`.

**Result:** Pipeline order is correct; priority does not determine flags; flags are independent; agreement rules are implemented as specified.

---

## Step 4 — Guard Rails

**Where:** [services/board_service.py](../services/board_service.py) `_evaluation_gate()` (136–153), invoked **before** agreement evaluation in `get_board()` (line 251).

**Behavior**

| Scenario               | Gate result         | Effect |
| ---------------------- | ------------------- | ------ |
| **Vacant Ready**       | `"vacant_ready"`    | `_build_healthy_board_item` with `agreements=AGREEMENTS_ALL_GREEN`, `priority="NORMAL"` → no violations. |
| **No move-out date**   | `"skip_evaluation"` | Same healthy item; no agreement evaluation → no violations. |
| **Cancelled turnover** | `"skip_evaluation"` | Same; no violations. |

Tests: [tests/services/test_board_service.py](../tests/services/test_board_service.py) (e.g. `test_guard_rail_vacant_ready_item_has_no_breach`, `test_guard_rail_no_move_out_produces_no_violations`, `test_guard_rail_cancelled_turnover_produces_no_violations`).

**Result:** Guard rails run before agreement evaluation; Vacant Ready, no move-out, and cancelled turnovers do not produce violations.

---

## Step 5 — Board Item Structure

**Source:** [services/board_service.py](../services/board_service.py) `get_board()` builds each item; `get_board_view()` delegates to `get_board()`.

**Board item fields:** turnover (with lifecycle fields), tasks, readiness (state, completed, total, blockers), sla (risk_level, days_until_breach, move_in_pressure), **agreements**, **priority**, unit, risks, notes.

**Agreements object:** From `evaluate_turnover_agreements()`: **inspection**, **sla**, **move_in**, **plan**, **viol**. Same set in `AGREEMENTS_ALL_GREEN` (lines 37–43). Guard-rail path uses `AGREEMENTS_ALL_GREEN` so agreements are always present.

**Result:** Board item structure matches spec; agreements include all five keys.

---

## Step 6 — Priority Engine

**Mapping** ([domain/priority_engine.py](../domain/priority_engine.py) `derive_priority_from_agreements`, 55–74)

- move_in RED → **MOVE_IN_DANGER**
- sla RED → **SLA_RISK**
- inspection RED → **INSPECTION_DELAY**
- plan RED → **PLAN_DELAY**
- else → **NORMAL**

Priority is derived from agreements only; it does not suppress or overwrite agreement flags. `viol` is an agreement flag but is not used in priority derivation (by design).

**Result:** Priority engine matches expected mapping; priority does not suppress agreement flags.

---

## Step 7 — Import Automation Layer (On Notice)

**Finding: "Import-to-lifecycle automation for On Notice units" is not implemented.**

- **No daily/scheduled job:** Imports run only when the user triggers the pipeline (e.g. Import Console → `import_service.run_import_pipeline()`). No cron or daily entrypoint.
- **Turnover creation from imports:** In [services/imports/available_units_service.py](../services/imports/available_units_service.py), turnover is created only when there is no open turnover and `status_allows_turnover_creation(raw_status)` is true. [domain/availability_status.py](../domain/availability_status.py) allows creation only for: vacant ready, vacant not ready, beacon ready, beacon not ready. **"On Notice" is not in that set**, so Available Units import does not create turnovers for On Notice rows.
- **No `available_date <= today` automation:** No code path that scans On Notice units, checks `available_date <= today`, and creates turnovers with the requested safeguards.

**Result:** Gap vs. stated refactor. The described "Import-to-lifecycle automation for On Notice units" (daily scan, available_date ≤ today, create turnovers with safeguards) would require new implementation (scheduler + logic + safeguards). See [docs/FULL_REGRESSION_AUDIT_FOLLOWUPS.md](FULL_REGRESSION_AUDIT_FOLLOWUPS.md) for documented gaps and optional follow-ups.

---

## Step 8 — UI Wiring

**Screens and data source**

- **Board** ([ui/screens/board.py](../ui/screens/board.py)): `board_service.get_board_view()`, `board_service.filter_by_flag_category()`, `board_service.get_board_metrics()`. Metrics from service; no local business logic.
- **Flag Bridge** ([ui/screens/flag_bridge.py](../ui/screens/flag_bridge.py)): `board_service.get_board_view()`, `board_service.has_any_breach()`, `board_service.get_flag_bridge_metrics()`. Renders agreement dots from `item.get("agreements")`. **Fallback:** If `agreements` is missing/empty (lines 166–177), UI derives breach flags from priority/sla/readiness. Primary path uses service data; fallback is defensive only.
- **Risk Radar** ([ui/screens/risk_radar.py](../ui/screens/risk_radar.py)): `risk_service.get_risk_dashboard()`; docstring states "no business logic in UI". Risk scoring in service.
- **Morning Workflow** ([ui/screens/morning_workflow.py](../ui/screens/morning_workflow.py)): `board_service.get_todays_critical_units()`, `board_service.get_morning_risk_metrics()`. Uses service read model.
- **Unit Detail** ([ui/screens/unit_detail.py](../ui/screens/unit_detail.py)): `unit_service.get_turnover_detail()`, `task_service.update_task()` / `complete_task()`. No domain imports in current codebase.

**Filters:** [ui/components/filters.py](../ui/components/filters.py) uses `board_service.get_board_filter_options()` for priority_order, phase_order, readiness_states (no direct domain imports).

**Result:** Screens use services for data and metrics. No UI→domain imports found. Flag Bridge has a defensive fallback when agreements are absent (board build always provides agreements in current code, so fallback is edge-case only).

---

## Step 9 — Data Consistency

**Checks performed (read-only)**

- **Tasks COMPLETED but missing completed_date:** Checked by [scripts/completed_date_consistency_check.py](../scripts/completed_date_consistency_check.py). Service logic ensures new completions get `completed_date`; legacy rows completed before the refactor could have `execution_status = 'COMPLETED'` and `completed_date IS NULL`. Run the script for detection; backfill is optional.
- **Units ready but with active violations:** Guard rails prevent Vacant Ready from getting violation flags; no code path found that would mark a unit ready while still evaluating it for breach.
- **Duplicate turnovers from automation:** N/A; On Notice automation does not exist. Existing creation paths (e.g. Available Units) use "no open turnover" and status checks; idempotent at batch level.
- **Flags for Vacant Ready:** Guard rail returns `"vacant_ready"` and builds healthy item with `AGREEMENTS_ALL_GREEN`; no violations.

**Known from prior audit** ([SYSTEM_AUDIT_RESULT.md](SYSTEM_AUDIT_RESULT.md)): 97 open turnovers with zero tasks (invariant: open turnovers should have tasks). Remediation is data/repair, not refactor wiring.

**Result:** No new consistency violations identified in layers. Optional: run completed_date consistency check and backfill if needed.

---

## Step 10 — System Health Summary

### Wiring and behavior

- **Database:** Task table has `completed_date`; old columns/constraint removed; migrations 008 and 009 applied in bootstrap.
- **Task lifecycle:** UI → task_service → repository → database; completed_date stamped once in service; no bypass.
- **Flag Bridge pipeline:** Guard rails → agreement evaluation → priority derivation → board rendering; flags independent; multiple red allowed.
- **Guard rails:** Run first; Vacant Ready, no move-out, cancelled produce no violations.
- **Board item:** Contains turnover, tasks, readiness, sla, agreements, priority; agreements include inspection, sla, move_in, plan, viol.
- **Priority engine:** Derived from agreements per mapping; does not suppress flags.
- **UI:** Uses services for data and metrics; no domain imports; Flag Bridge has defensive fallback when agreements absent.

### Gaps and notes

1. **On Notice import automation:** Not implemented. No daily scan of On Notice units, no `available_date <= today` turnover creation with the described safeguards. Document as out-of-scope or implement separately (see [FULL_REGRESSION_AUDIT_FOLLOWUPS.md](FULL_REGRESSION_AUDIT_FOLLOWUPS.md)).
2. **Flag Bridge fallback:** When `agreements` is missing/empty, UI infers breach from priority/sla/readiness. Acceptable as defensive fallback; normal path always has agreements.
3. **Schema on existing DBs:** If a database was created before 008/009 were in bootstrap, run migrations once or rely on next app startup (current code applies 008 and 009 in `ensure_database_ready()`).
4. **Data:** 97 open turnovers without tasks (from prior audit); consider repair or documented exception.

### Conclusion

The refactor is **stable and correctly wired** for:

- Task completion and `completed_date`
- Flag Bridge evaluation order and agreement-based priority
- Guard rails and board structure
- UI consuming services only

**Production readiness:** Yes, for the implemented features. The only substantive gap is the **missing On Notice import-to-lifecycle automation**; if that was a committed product requirement, it should be added as a separate feature (scheduler + creation logic + safeguards). No layers bypass services; no inconsistent data flows were found in code.

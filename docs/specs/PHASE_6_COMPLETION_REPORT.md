# Phase 6 — Import-to-Lifecycle Automation Layer: Completion Report

**Date:** 2026-03-16

## 1. Where the automation was implemented

- **Service:** [services/lifecycle_automation_service.py](services/lifecycle_automation_service.py)
- **Entry points:**
  - `run_available_date_transition(property_id, today=None, phase_ids=None)` — runs for a single property; returns `{"transitioned": int, "errors": list}`.
  - `run_available_date_transition_all_properties(today=None)` — runs for all properties via `property_repository.get_all()`; returns `{"total_transitioned", "by_property", "errors"}`.

The automation is designed to be invoked once daily (e.g. at midnight) by an external scheduler (cron, Celery, etc.). No scheduler is implemented inside the app.

---

## 2. How eligible units are identified

- **Source:** Open turnovers for the property from `turnover_repository.get_open_by_property(property_id, phase_ids=phase_ids)`.
- **Eligibility filter (in Python):** A turnover is eligible when **all** of the following hold:
  - `manual_ready_status == "On Notice"`
  - `available_date is not None` and `available_date <= today`
  - Open turnover (already guaranteed by `get_open_by_property`: `closed_at IS NULL`, `canceled_at IS NULL`)

No new repository method was added; filtering is done in the service after fetching open turnovers.

---

## 3. How duplicate turnovers are prevented

- The automation **does not create** new turnovers. It only **updates** existing open turnovers from On Notice → Vacant Not Ready.
- **Idempotency:** After a turnover is transitioned, its `manual_ready_status` becomes `"Vacant Not Ready"`, so it is no longer selected on a subsequent run. Re-running the automation does not create a second turnover or duplicate tasks (`ensure_turnover_has_tasks` only adds tasks when the turnover has zero tasks; `task_service.instantiate_templates` skips existing task types).

---

## 4. How audit history is written

- For each transition, the service:
  1. Calls `turnover_service.update_turnover(turnover_id, actor="system", manual_ready_status="Vacant Not Ready", availability_status="vacant not ready")`, which writes audit rows for the changed fields (source `"turnover_service"`).
  2. Calls `turnover_service.ensure_turnover_has_tasks(turnover_id, actor="system")` (which may write audit when it generates tasks).
  3. Writes an explicit automation audit entry via `audit_repository.insert()` with:
     - `entity_type="turnover"`, `entity_id=turnover_id`, `property_id` from the turnover
     - `field_name="lifecycle_transition"`
     - `old_value="On Notice"`, `new_value="On Notice → Vacant Not Ready by import automation layer"`
     - `actor="system"`, **`source="import automation layer"`**

---

## 5. Results of verification scenarios

| Scenario | Description | Result |
|----------|-------------|--------|
| **A — Eligible unit** | Open turnover: `manual_ready_status='On Notice'`, `available_date=today`, no tasks | **PASS:** Status transitions to Vacant Not Ready; `update_turnover` and `ensure_turnover_has_tasks` called; audit with `source="import automation layer"` written. |
| **B — Future available date** | `manual_ready_status='On Notice'`, `available_date > today` | **PASS:** No transition; `update_turnover` not called. |
| **C — Turnover already Vacant Not Ready** | Same as A but status already Vacant Not Ready | **PASS:** Not selected; no update. |
| **D — Not On Notice** | `manual_ready_status` in (`Vacant Ready`, `None`) | **PASS:** No transition. |
| **E — Repeat execution** | Run automation twice; after first run unit is Vacant Not Ready | **PASS:** Second run does not select that turnover; no duplicate tasks or turnover. |

Additional test: turnover with On Notice but `available_date is None` is not eligible — **PASS.**

Tests live in [tests/services/test_lifecycle_automation_service.py](tests/services/test_lifecycle_automation_service.py). All 21 tests (7 lifecycle automation + 14 availability_status) pass.

---

## 6. Prerequisite: Import layer (On Notice creation and manual_ready_status sync)

To have turnovers in "On Notice" for the automation to transition, the following was implemented:

- **Domain** [domain/availability_status.py](domain/availability_status.py):
  - `status_is_on_notice(status)` — True for `"on notice"`, `"on notice (break)"`.
  - `availability_status_to_manual_ready_status(raw_status)` — Maps normalized import status to canonical `'On Notice'`, `'Vacant Not Ready'`, `'Vacant Ready'` (or None).

- **Available Units import** [services/imports/available_units_service.py](services/imports/available_units_service.py):
  - Rows with status **on notice** (or on notice (break)) and a valid unit now create a turnover when none exists (same as vacant/beacon), with `move_out_date = available_date`, and set `manual_ready_status` and `availability_status` on create.
  - On **update**, when `availability_status` is applied from the file, `manual_ready_status` is synced from the same mapping so lifecycle and automation stay aligned.

This ensures that after an Available Units import, "On notice" units with an available date have an open turnover with `manual_ready_status = 'On Notice'`, which the midnight automation can then transition to Vacant Not Ready when `available_date` has arrived.

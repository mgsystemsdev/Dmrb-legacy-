# Full Regression Audit — Gaps and Follow-ups

This document records gaps and optional follow-ups from the [FULL_REGRESSION_AUDIT_REPORT.md](FULL_REGRESSION_AUDIT_REPORT.md). No code changes were made during the audit.

---

## 1. On Notice import-to-lifecycle automation (gap)

**Status:** Not implemented.

**Description:** The refactor list included "Import-to-lifecycle automation for On Notice units". The codebase does not implement:

- A daily (or scheduled) job that runs without user action
- A scan of units in an "On Notice" state
- A check that `available_date <= today`
- Creation of turnovers when the above hold, with safeguards:
  - Unit must still be On Notice
  - No open turnover already exists for the unit
  - Unit must not be Vacant Ready
  - Automation must be idempotent

**Current behavior:** Imports run only when the user triggers the pipeline (e.g. Import Console). Turnover creation from the Available Units import uses `status_allows_turnover_creation()` in [domain/availability_status.py](../domain/availability_status.py), which allows only: vacant ready, vacant not ready, beacon ready, beacon not ready. "On Notice" is not in that set, so no turnovers are created for On Notice rows from that import.

**Recommendation:** Treat as out-of-scope for the audit, or implement as a separate feature: add a scheduled entrypoint (cron or similar), a service that selects On Notice units with `available_date <= today`, and creation logic with the safeguards above.

---

## 2. Completed-date consistency check (implemented)

**Status:** Implemented as optional follow-up.

**Description:** Tasks with `execution_status = 'COMPLETED'` and `completed_date IS NULL` can exist if they were completed before the refactor. The audit recommended an optional consistency check.

**Implementation:** [scripts/completed_date_consistency_check.py](../scripts/completed_date_consistency_check.py)

- Read-only: selects `task_id`, `turnover_id`, `task_type`, `vendor_completed_at` for rows where `execution_status = 'COMPLETED'` and `completed_date IS NULL`.
- Exit 0 if none; exit 1 if any (suitable for CI or ops).
- Optional backfill: set `completed_date = vendor_completed_at::date` for those rows (not performed by the script).

**Usage:** From project root, with `DATABASE_URL` set:

```bash
python scripts/completed_date_consistency_check.py
```

---

## 3. Other notes (no action required)

- **Flag Bridge fallback:** When `agreements` is missing/empty on a board item, the UI derives breach flags from priority/sla/readiness. The board build always supplies agreements, so this is a defensive edge-case only; no change required.
- **Schema on existing DBs:** If a database was created before migrations 008/009 were in bootstrap, run those migrations once or rely on the next app startup; `ensure_database_ready()` in [db/connection.py](../db/connection.py) applies both.
- **97 open turnovers without tasks:** Documented in [SYSTEM_AUDIT_RESULT.md](SYSTEM_AUDIT_RESULT.md). **Layer 3 backfill implemented:** a dedicated process scans all open turnovers and ensures each has tasks.

---

## 4. Layer 3 — Task backfill (implemented)

**Status:** Implemented.

**Description:** Layer 3 (Backfill / system integrity) ensures the invariant “every open turnover has tasks” even when Layer 1 (creation) or Layer 2 (Unit Detail self-heal) did not run (e.g. legacy data, unit without phase at creation).

**Implementation:**

- **Service:** [services/turnover_service.py](../services/turnover_service.py) — `backfill_tasks_for_property(property_id, phase_ids=None)` and `backfill_tasks_all_properties(phase_ids_by_property=None)`. Each calls `ensure_turnover_has_tasks` for every open turnover (no-op when tasks already exist).
- **CLI:** [scripts/backfill_turnover_tasks.py](../scripts/backfill_turnover_tasks.py) — Run from project root with `DATABASE_URL` set (env or `.streamlit/secrets.toml`). Optional `--property-id N` to run for one property only.

**Usage:**

```bash
python scripts/backfill_turnover_tasks.py
python scripts/backfill_turnover_tasks.py --property-id 1
```

**Scheduling:** Run periodically (e.g. daily after lifecycle automation or weekly), e.g.:

```bash
0 1 * * * cd /path/to/app && DATABASE_URL=... python scripts/backfill_turnover_tasks.py
```

Exit 0 if no errors; exit 1 if any turnover failed (suitable for cron alerting).

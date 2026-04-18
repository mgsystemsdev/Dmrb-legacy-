# Phase Scope Diagnostic Report

## Chain traced

```
Admin UI → scope_service.update_phase_scope()
         → scope_service.get_phase_scope()
         → service read models (board, risk, unit, task)
         → repository SQL (turnover, unit)
         → filtered results
```

---

## Step 1 — Scope persistence

**Status: Correct**

- **scope_service.update_phase_scope(property_id, phase_ids)** calls:
  - `phase_scope_repository.upsert(property_id, user_id=None)` → inserts/updates `phase_scope`, returns row.
  - `phase_scope_repository.set_phases(scope_row["id"], phase_ids)` → DELETE from `phase_scope_phase` then INSERT one row per `phase_id`.
- **phase_scope_repository**: Uses `get_connection()` with `autocommit=True`, so each execute commits. Rows are written to `phase_scope` and `phase_scope_phase`.
- **Admin UI** (admin.py): On "Apply Phase Scope", builds `selected_ids` from multiselect codes via `phase_id_by_code`, calls `scope_service.update_phase_scope(property_id, selected_ids)`, then `st.cache_data.clear()` and `st.rerun()`.

**Conclusion:** Persistence path is correct. If the DB has the tables and the button is used, rows should be written.

---

## Step 2 — Scope resolution

**Status: Correct (with one caveat)**

- **scope_service.get_phase_scope(property_id)**:
  - Reads `scope_row = phase_scope_repository.get_by_property(property_id)`.
  - If `scope_row is None`: returns all `phase_id`s for the property (from `property_repository.get_phases`).
  - If scope row exists: loads `phase_scope_repository.get_phase_ids(scope_row["id"])`, validates each id against the property, returns the list.

**Caveat:** If `get_by_property` always returns `None` (e.g. table missing, wrong DB, or row not visible), then `get_phase_scope` will always return **all phases**. That would explain "operational views still show all phases" after configuring scope.

**Temporary debug:** Added `print` in `get_phase_scope` to log whether a scope row was found and what was returned. Run the app, set a restricted scope in Admin, then open Board and check the terminal:
- If you see `no scope row → returning all phases` after saving a restricted scope, the break is in **persistence or read** (row not written or not found).
- If you see `stored_ids=[...] → resolved: [...]` with the subset you selected, resolution is correct and the break is downstream.

---

## Step 3 — Service calls

**Status: Correct**

| Service | Function | Accepts phase_scope? | Resolves when None? |
|---------|----------|----------------------|----------------------|
| board_service | get_board_view | Yes | Yes: `scope_service.get_phase_scope(property_id)` |
| board_service | get_board | Yes | No (caller must pass or use get_board_view) |
| board_service | get_board_metrics, get_flag_counts, get_flag_units, get_morning_risk_metrics, get_todays_critical_units | Yes | Yes: resolve then call get_board with scope |
| risk_service | get_risk_dashboard | Yes | Yes: resolve then call board_service.get_board with scope |
| unit_service | get_units | Yes | Yes: resolve then repo with phase_ids |
| task_service | get_schedule_rows | Yes | Yes: resolve then turnover/unit repos with phase_scope |

All operational services either accept `phase_scope` or resolve it when `None`. No service was found that ignores scope.

---

## Step 4 — Repository query filtering

**Status: Correct**

- **turnover_repository.get_open_by_property(property_id, phase_ids=None)**  
  When `phase_ids is not None`: uses `JOIN unit u ... AND u.phase_id = ANY(%s)`. Filtering is in SQL.

- **unit_repository.get_by_property(property_id, active_only=True, phase_ids=None)**  
  When `phase_ids is not None`: adds `AND phase_id = ANY(%s)`. Filtering is in SQL.

No repository was found that loads all rows and filters in Python.

---

## Step 5 — Services passing scope to repositories

**Status: Correct**

- **board_service.get_board**: Passes `phase_scope` as `phase_ids=phase_scope` to `turnover_repository.get_open_by_property` and `unit_repository.get_by_property`.
- **task_service.get_schedule_rows**: Passes `phase_scope` as `phase_ids=phase_scope` to the same two repos.

Scope is passed through; no missing parameters found.

---

## Step 6 — UI not filtering

**Status: Correct**

- **board.py**: Resolves `phase_scope = scope_service.get_phase_scope(property_id)`, calls `_load_board(property_id, tuple(sorted(phase_scope)))` which calls `board_service.get_board_view(property_id, phase_scope=...)`. No UI-side phase filter.
- **risk_radar.py**: Resolves `phase_scope`, calls `_load_risk_dashboard(property_id, tuple(sorted(phase_scope)))` which calls `risk_service.get_risk_dashboard(property_id, phase_scope=...)`. No UI filter.
- **morning_workflow.py**, **flag_bridge.py**: Same pattern; scope is resolved and passed into services. No UI filtering.

---

## Step 7 — Where propagation can stop

Given the code review, the only plausible break points are:

### A. Scope row not found (get_phase_scope always returns all phases)

- **File:** `services/scope_service.py`  
- **Function:** `get_phase_scope(property_id)`  
- **Reason:** If `phase_scope_repository.get_by_property(property_id)` always returns `None`, the function returns all phases. That happens if:
  - The `phase_scope` table does not exist (migration not applied).
  - The row was never written (e.g. Admin "Apply" not clicked, or exception in update_phase_scope).
  - A different DB/schema is used for read vs write.

**Minimal check:** Run the app, go to Admin → Phase Manager, select a subset of phases, click "Apply Phase Scope". Then in DB: `SELECT * FROM phase_scope;` and `SELECT * FROM phase_scope_phase;`. If rows exist and `get_phase_scope` still logs "no scope row", the read is using a different connection or schema.

### B. Streamlit cache serving stale board data

- **File:** `ui/screens/board.py` (and similarly flag_bridge, risk_radar)  
- **Function:** `_load_board(property_id, phase_scope: tuple[int, ...])`  
- **Reason:** `@st.cache_data(ttl=30)` keys on `(property_id, phase_scope)`. If the UI ever passed the same tuple as before (e.g. always the full list of phase ids), the cached "all phases" result would be reused.  
- **Code path:** `phase_scope = scope_service.get_phase_scope(property_id)` then `_load_board(property_id, tuple(sorted(phase_scope)))`. If `get_phase_scope` returns all phases (see A), the cache key is the same as for "all phases" and the cached full-property board is returned.

So **A is the root cause** if it holds; **B** is a consequence of A (wrong cache key because scope resolution is wrong).

### C. Empty tuple passed as scope

- **File:** `ui/screens/board.py`  
- **Function:** `_load_board`  
- **Code:** `phase_scope=list(phase_scope) if phase_scope else None`  
- **Reason:** When saved scope is `[]`, the UI passes `()`. Then `phase_scope` is falsy, so `None` is passed to `get_board_view`. That triggers resolution again (correct). So this does not cause "show all phases"; at most it affects the "no phases selected" case.

---

## Recommended minimal corrections

1. **Confirm persistence and resolution**  
   Use the temporary debug prints in `scope_service.get_phase_scope` and `board_service.get_board_view`. After saving a restricted scope in Admin and opening Board, check the terminal:
   - If you see `no scope row → returning all phases`: fix persistence/read (ensure migration applied, same DB, and that Apply actually runs `update_phase_scope`).
   - If you see the correct `stored_ids` and `resolved` list but the board still shows all phases, then the bug is in a path not yet traced (e.g. a different code path loading the board).

2. **Ensure migration 005 is applied**  
   Ensure `phase_scope` and `phase_scope_phase` exist in the DB used at runtime (e.g. run `db/migrations/005_phase_scope.sql` or rely on `ensure_database_ready()` applying it).

3. **Remove debug logging**  
   After confirming, remove the `print` statements added in `scope_service.get_phase_scope` and `board_service.get_board_view`.

No architectural changes, new abstractions, or refactors are required; the chain is correct. The failure is most likely **scope row not present or not read**, so `get_phase_scope` always returns all phases and the rest of the chain behaves as "no scope configured."

---

## Runtime instrumentation (temporary [DIAG] logs)

Temporary diagnostics have been added so you can collect evidence at runtime. **Restart the app** and use Admin to set scope, then open Board/Risk Radar. Watch the terminal for lines starting with `[DIAG]`.

### What is logged

| Step | Location | Log prefix | Meaning |
|------|----------|------------|---------|
| 1–2 | `db/connection.py` (once at first `get_connection()`) | `[DIAG] DATABASE_URL (masked):` | Which DB URL the app uses (password masked). |
| | | `[DIAG] DSN:` | Connection DSN string. |
| | | `[DIAG] DB identity:` | `current_database`, `current_schema`. |
| | | `[DIAG] phase_scope tables present:` | Whether `phase_scope` and `phase_scope_phase` exist. |
| | | `[DIAG] phase_scope rows:` | Contents of `phase_scope` at startup. |
| | | `[DIAG] phase_scope_phase rows:` | Contents of `phase_scope_phase` at startup. |
| 3 | `ui/screens/admin.py` | `[DIAG] Writing phase scope:` | Admin: property_id, selected_codes, phase_ids when Apply is clicked. |
| | `services/scope_service.py` | `[DIAG] update_phase_scope:` | Service write: property_id, phase_ids. |
| | `db/repository/phase_scope_repository.py` | `[DIAG] Write DSN (upsert):` | DSN used for the write. |
| | | `[DIAG] Inserted scope row:` | Row returned by upsert. |
| 4 | `services/scope_service.py` | `[DIAG] Reading phase scope for property_id:` | Read requested for which property. |
| | | `[DIAG] Scope row:` | What the service got from the repo (or None). |
| | | `[DIAG] Scope phase ids:` | Resolved list of phase_ids returned. |
| | `db/repository/phase_scope_repository.py` | `[DIAG] Read DSN (get_by_property):` | DSN used for get_by_property. |
| | | `[DIAG] Scope row (repo):` | Raw row from `phase_scope`. |
| | | `[DIAG] Read DSN (get_phase_ids):` | DSN used for get_phase_ids. |
| | | `[DIAG] Scope phase ids (repo):` | Raw phase_ids from `phase_scope_phase`. |
| 5 | `services/board_service.py` | `[DIAG] Board query phase_scope (get_board_view):` | Scope passed into board view. |
| | | `[DIAG] Board query phase_scope (get_board):` | Scope passed into get_board. |
| | `db/repository/turnover_repository.py` | `[DIAG] Repository phase_ids:` | phase_ids passed to turnover repo. |
| | | `[DIAG] SQL params:` | property_id and phase_ids used in the query. |
| 6 | `ui/screens/board.py` | `[DIAG] Board cache key:` | property_id and phase_scope tuple used as cache key. |
| | `ui/screens/risk_radar.py` | `[DIAG] Risk dashboard cache key:` | Same for risk dashboard. |

### How to interpret (root cause)

- **Case A — Scope rows never written**  
  After clicking Apply in Admin you do **not** see `[DIAG] Inserted scope row:` with a non-None row, or startup `phase_scope rows:` / `phase_scope_phase rows:` stay empty.  
  **Fix:** Ensure Apply runs (no exception), migration 005 applied, and the app is connected to the DB you expect.

- **Case B — Write and read use different DB**  
  `[DIAG] Write DSN (upsert):` and `[DIAG] Read DSN (get_by_property):` (or `Read DSN (get_phase_ids):`) show **different** host/dbname/user.  
  **Fix:** Use a single source for `DATABASE_URL` (env or Streamlit secrets); ensure no other process or config overrides it.

- **Case C — Scope read correctly but board still shows all phases**  
  Logs show correct `Scope phase ids:` and `Board query phase_scope:` and `Repository phase_ids:` with a subset (e.g. `[3, 4, 5]`), but the UI still shows all phases.  
  **Fix:** Then filtering is applied; check for another code path that loads board without scope (or remove duplicate/legacy loads).

- **Case D — Cache returns stale results**  
  You change scope in Admin and see a new `Scope phase ids:` (e.g. `[3, 4, 5]`), but `Board cache key:` still shows the old tuple (e.g. all phase ids). So the cache key did not change.  
  **Fix:** Ensure the Board screen uses `phase_scope = scope_service.get_phase_scope(property_id)` and passes `tuple(sorted(phase_scope))` into `_load_board`; if the key still matches an old full scope, the bug is that `get_phase_scope` is returning the old value (see Case A/B).

### Evidence report template (fill after running)

After one run (start app → set scope in Admin → open Board), copy from the terminal and fill:

```
Active database identity:
  [DIAG] DB identity: current_database=? current_schema=?

Phase scope tables present or missing:
  [DIAG] phase_scope tables present: ?

Rows currently stored in phase_scope (at startup):
  [DIAG] phase_scope rows: ?

Rows stored in phase_scope_phase (at startup):
  [DIAG] phase_scope_phase rows: ?

DSN used for write operations:
  [DIAG] Write DSN (upsert): ?

DSN used for read operations:
  [DIAG] Read DSN (get_by_property): ?

Resolved phase scope used by board:
  [DIAG] Board query phase_scope (get_board_view): ?
  [DIAG] Board query phase_scope (get_board): ?

SQL parameters used in board queries:
  [DIAG] SQL params: property_id=? phase_ids=?

Cache keys used by Streamlit:
  [DIAG] Board cache key: property_id=? phase_scope=?
```

Compare write DSN vs read DSN; confirm phase_scope and SQL params match the scope you set; confirm cache key changes when you change scope. Remove all `[DIAG]` prints once the root cause is fixed.

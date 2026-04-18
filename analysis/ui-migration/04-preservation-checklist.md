# DMRB Legacy — Critical UI Behaviors Preservation Checklist

> These behaviors must be reproduced with functional parity in any migration.
> Check each item verified in the new implementation before declaring a screen complete.
> Analysis date: 2026-04-17

---

## Global Shell

- [ ] **Property-scoped world**: Every screen that renders operational data must first assert `property_id` is set. Wrong scope = wrong data. Null property → show "Select a property" message, render nothing.
- [ ] **Phase scope filter**: `scope_service.get_phase_scope()` returns active phase IDs. Board, schedule, morning workflow, and sidebar flags must all be filtered by this. Phase scope changes affect all users of that property simultaneously.
- [ ] **Sidebar always rendered**: Sidebar renders on every page load (property selector, nav, flags). It is never conditional on the current page.
- [ ] **Property selector in sidebar**: Changing property immediately re-scopes the entire app for that session. Must trigger data reload.
- [ ] **Top Flags (sidebar)**: Data-driven per-property flag queue rendered below nav. Each flag must navigate to the correct unit's detail page.

---

## Authentication & Authorization

- [ ] **Three auth modes functional**: `AUTH_DISABLED`, `LEGACY_AUTH_SOURCE=env`, `LEGACY_AUTH_SOURCE=db` must all work. DB auth assigns `user_id`, `username`, and `access_mode` from the `app_user` table.
- [ ] **`access_mode=validator_only`**: Must restrict navigation to W/O Validator screen only. Sidebar hides all other nav. Router enforces this even if URL is manually changed.
- [ ] **`access_mode=full`**: Full nav, no restrictions.
- [ ] **Empty DB user table messaging**: When `LEGACY_AUTH_SOURCE=db` and `app_user` table is empty, show actionable message (not generic auth error).
- [ ] **DB writes master switch**: `admin.py` checkbox reflects DB state on each load. Toggle persists to DB. When OFF, all write operations across all screens show a warning instead of saving. No silent failures.

---

## Board Screen

- [ ] **`board_filter` passthrough**: If `board_filter` session key is set (by Morning Workflow or Risk Radar), board shows only the filtered subset with a blue banner identifying the active filter. "Clear Filter" button removes it and reruns.
- [ ] **Live filters**: All board filter widgets (search, phase, status, N/V/M, QC, assignee) apply immediately on change — no "Apply" button.
- [ ] **Unit Info tab**: 5 editable columns (Status, Move-Out, Ready Date, Move-In, QC). All other columns read-only. `SelectboxColumn` for Status and QC, `DateColumn` for dates.
- [ ] **QC Guard**: If any board row lacks a QUALITY_CONTROL task, the QC column is disabled for the entire table, with a caption explaining why.
- [ ] **Unit Tasks tab**: Columns dynamically built from task types present on current board rows, ordered by `TASK_COLS` with extras appended. Each task gets a paired date column.
- [ ] **▶ Row-select navigation**: Checking the ▶ checkbox on any row navigates to that turnover's unit detail. `tid_list` alignment must be stable (not broken by sort/filter changes).
- [ ] **Inline mutation persistence**: Status, date, QC changes persist to DB on save. After save: editor key reset, cache cleared, page reruns.
- [ ] **`actor="board"` and `source="board_inline_edit"`**: All board mutations must include these audit fields.

---

## Unit Detail Screen

- [ ] **Lookup mode**: When `selected_turnover_id is None`, show search input. On match, navigate to detail.
- [ ] **Back button**: Clears `selected_turnover_id`, `board_info_editor`, `board_task_editor` from session. Returns to board.
- [ ] **On-change autosave**: Status selectbox, date inputs, legal toggle all save immediately on change. No save button required. **No `st.rerun()` inside callbacks** — Streamlit/framework triggers automatically.
- [ ] **Legal dot**: 🟢 when `legal_confirmed_at` set, 🔴 when not. Toggle immediately sets or clears `legal_confirmed_at` and `legal_confirmation_source`.
- [ ] **Status options**: `["Vacant ready", "Vacant not ready", "On notice"]` only. Mapping to DB fields must match `board_table.py`'s `_board_status_to_db()` exactly.
- [ ] **Task grid**: All task types for this turnover rendered as rows. Columns: Task | Assignee | Date | Execution | Completed At | Req | Blocking.
- [ ] **Extended execution labels**: Unit detail task selectbox uses `EXEC_LABELS_EXTENDED` (6 options including N/A, Canceled). Board uses basic `EXEC_LABELS` (4 options).
- [ ] **EXEC_SIDE_EFFECTS**: Selecting "N/A" auto-sets `required=False`. Selecting "Canceled" auto-sets `required=False` and `blocking=False`.
- [ ] **Carpet status cycling**: CARPET task row shows a button cycling `["Carpet", "No Carpet", "Carpet Replacement"]` with emoji indicators.
- [ ] **W/D status flow**: Mark Notified → Mark Installed sequence enforced (Install disabled until Notified). Undo Notified / Undo Installed buttons must reverse actions.
- [ ] **Notes**: Display with severity icons, resolve button, add new note with severity selectbox.
- [ ] **Authority & Import Comparison expander**: Shows 4-field comparison table (Move-Out, Move-In, Status, Legal Confirmed) with source of truth column.
- [ ] **Audit history expander**: Shows all field changes with date, actor, source, old/new values.
- [ ] **Cancel Turnover**: Only shown when `is_open == True`. Clears session state and returns to board.
- [ ] **`actor="manager"` and `source="unit_detail_autosave"`**: All unit detail mutations must include these audit fields.

---

## Operations Schedule

- [ ] **Manager view**: Editable table with Date, Assignee, Status columns. Task type filter multiselect. Explicit "Save Changes" button for batch update.
- [ ] **Vendor view**: Read-only table — no editing affordance. Clean layout for vendor coordination.
- [ ] **Sort order**: Tasks sorted by `TASK_PIPELINE_ORDER` priority first, then by `vendor_due_date`.
- [ ] **`actor="manager"`**: All schedule mutations must include this.

---

## Morning Workflow

- [ ] **Top action buttons → board navigation**: "Move-In Danger" and "SLA Risk" buttons set `board_filter` and navigate to board. "Repair Queue" button sets `mw_focus_repair_queue` flag and stays on morning workflow.
- [ ] **Repair queue focus hint**: `mw_focus_repair_queue` one-shot flag triggers info banner in repair queue section on next render. Must be popped on read.
- [ ] **Missing Move-Out editor**: Editable `DateColumn` in "Missing Move-Outs" table. After entering dates, creates turnovers and reruns. Unit/Move-In/Report columns read-only.
- [ ] **Critical unit drill-in**: Buttons in critical units section navigate to unit detail via `selected_turnover_id`.
- [ ] **Risk metrics navigation**: Metric buttons navigate to board (with `board_filter`) or flag_bridge.

---

## Flag Bridge

- [ ] **▶ checkbox navigation**: Same pattern as board — checking row navigates to unit detail.
- [ ] **Breach filter categories**: "Insp Breach", "SLA Breach", "SLA MI Breach", "Plan Breach" map to breach detection logic.
- [ ] **Read-only table**: No mutations on flag bridge — view only.
- [ ] **Complex breach detection logic**: Must use agreements RED flags first; fall back to priority/SLA/readiness for older phases.

---

## Export Reports

- [ ] **Prepare-then-download flow**: "Prepare Export Files" button must run first. Download buttons appear after. Bytes stored server-side (not in client session for scale).
- [ ] **5 download formats**: Weekly Summary (TXT), Final Report (XLSX), DMRB Report (XLSX), Dashboard Chart (PNG), All Reports (ZIP).
- [ ] **Error display**: `export_prepare_error` shown persistently until next successful prepare.
- [ ] **No download before prepare**: Download buttons disabled/empty when bytes not prepared.

---

## Admin Screen

- [ ] **DB writes toggle synced from DB**: Checkbox value reads from DB on every page load. Not from widget default alone.
- [ ] **Phase scope applies globally**: Caption must document that phase scope changes affect all users of the property.
- [ ] **Flash messages**: Admin user operations (create, password update, role change) use one-shot session flash. Pop on read.
- [ ] **Unit master CSV validation**: Validate column presence before import attempt. Show result summary (rows created/skipped).
- [ ] **Create property flow**: After creation, set `property_id`, clear cache, rerun.

---

## Status & QC Mapping Invariants

These mappings must be **identical** across all screens that write status:

| Board Label | DB `manual_ready_status` | DB `availability_status` |
|-------------|--------------------------|--------------------------|
| `"Vacant ready"` | `MANUAL_READY_VACANT_READY` | `"vacant ready"` |
| `"Vacant not ready"` | `MANUAL_READY_VACANT_NOT_READY` | `"vacant not ready"` |
| `"On notice"` | `MANUAL_READY_ON_NOTICE` | `"on notice"` |

QC mapping:

| QC Label | `execution_status` |
|----------|--------------------|
| "QC Done", "Confirmed" | `COMPLETED` |
| "QC Not Done", "Pending" | `NOT_STARTED` |

These appear in **both** `board_table.py` (inline) and `unit_detail.py`. Any migration must centralize them in a single service or constants layer.

---

## Session Key Lifecycle

| Key | Written by | Cleared by | Behavior |
|-----|-----------|-----------|---------|
| `selected_turnover_id` | Board ▶, Flag Bridge ▶, sidebar flags, Morning Workflow | Unit detail back button, Cancel Turnover | Must be cleared on "back" to prevent stale unit detail |
| `board_info_editor` | Streamlit widget init | Unit detail back + board mutations | Must be popped to reset grid to fresh data |
| `board_task_editor` | Streamlit widget init | Unit detail back button | Must be popped; currently NOT popped after task mutations (known gap) |
| `board_filter` | Morning Workflow, Risk Radar | Board "Clear Filter" button | Pre-filter passthrough; clear button must pop the key |
| `mw_focus_repair_queue` | Morning Workflow top button | Morning Workflow on read | Pop on read to prevent re-showing on every rerun |

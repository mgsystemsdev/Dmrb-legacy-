# DMRB Legacy — Complete UI Architecture Report

> Source: Live codebase under `app.py` and `ui/`. Not `docs/legacy/` or `docs/export_reference`.
> Analysis date: 2026-04-17

---

## 1. Application Shell & Bootstrap

**Entry sequence (`app.py:14-19`):**

```
st.set_page_config(page_title="DMRB", layout="wide")
init_session_state()       → sets all default session keys
bootstrap_backend()        → @st.cache_resource DB migration check
render_sidebar()           → always rendered (property + nav + flags)
route_page()               → auth gate + page dispatch
```

**Framework-agnostic model:** single layout shell (sidebar + main content area), global bootstrap (DB/migration readiness), then a router that selects a view controller based on session-backed route state.

---

## 2. Navigation & Routing

**Pattern: session-string router (no URL routing)**

File: `ui/router.py`

- `route_page()` calls `require_auth()` → `st.stop()` on failure
- Enforces `access_mode == "validator_only"` → forces `current_page = "work_order_validator"`
- Dispatches on `st.session_state.get("current_page", "board")` with lazy imports per screen
- Default landing: `board`

**15 screens dispatched:**

| `current_page` | Module | Role |
|----------------|--------|------|
| `unit_detail` | `unit_detail.py` | Deep turnover view; lookup mode if no selection |
| `import_reports` | `import_reports.py` | Report Operations (tabs) |
| `flag_bridge` | `flag_bridge.py` | Breach grid + row-select navigation |
| `add_turnover` | `add_turnover.py` | Wizard-style add + jump to detail |
| `property_structure` | `property_structure.py` | Structure admin |
| `morning_workflow` | `morning_workflow.py` | Daily command center |
| `risk_radar` | `risk_radar.py` | Sorted risk table |
| `ai_agent` | `ai_agent.py` | Chat UI |
| `work_order_validator` | `work_order_validator.py` | Uploads + exports |
| `operations_schedule` | `operations_schedule.py` | Manager vs vendor schedule |
| `admin` | `admin.py` | DB writes toggle, property create, 4 tabs |
| `repair_reports` | `repair_reports.py` | Repair report view |
| `import_console` | `import_console.py` | Import flows |
| `export_reports` | `export_reports.py` | Prepare + download hub |
| (default) | `board.py` | Main operational board |

---

## 3. Sidebar Architecture

File: `ui/components/sidebar.py`

**Layout blocks (top → bottom):**
1. Branding — `st.markdown(unsafe_allow_html=True)` for styled `<h2>` + subtitle
2. Property selector — `st.selectbox` → writes `st.session_state.property_id`
3. Navigation — expander groups OR validator-only mode
4. Top Flags — data-driven drill-in to unit detail

**`_NAV_GROUPS` structure:**

```python
[
  ("Quick Tools", True, [
      ("➕ Add Turnover",    "add_turnover"),
      ("🔍 Unit Lookup",     "unit_detail"),
      ("🤖 DMRB AI Agent",  "ai_agent"),
  ]),
  ("Daily Ops", True, [
      ("🌅 Morning WF",      "morning_workflow"),
      ("📋 DMRB Board",      "board"),
      ("📅 Ops Schedule",    "operations_schedule"),
      ("🚩 Flag Bridge",     "flag_bridge"),
      ("📡 Risk Radar",      "risk_radar"),
      ("🔧 W/O Validator",  "work_order_validator"),
  ]),
  ("Import & Reports", True, [
      ("📥 Import Reports",  "import_console"),
      ("🛠 Repair Reports",  "repair_reports"),
      ("Export Reports",     "export_reports"),
  ]),
  ("Administration", False, [
      ("📥 Report Operations", "import_reports"),
      ("🏗️ Structure",         "property_structure"),
      ("⚙️ Admin",             "admin"),
  ]),
]
```

**Validator-only mode:** Hides all nav groups; shows only "🔧 W/O Validator" button.

**Navigation button behavior:**
- Key: `f"nav_btn_{page_key}"`
- `type="primary"` when `current_page == page_key`
- On click: sets `current_page`, **clears `selected_turnover_id`** if entering `unit_detail` from another page, calls `st.rerun()`

**Top Flags:** `board_service.get_flag_units` → expanders per category → unit buttons set `selected_turnover_id + current_page = "unit_detail"` + rerun.

---

## 4. Session State

**Initialization (`ui/state/session.py`):**

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `authenticated` | bool | False | User auth status |
| `access_mode` | str/None | None | `"full"` or `"validator_only"` |
| `user_id` | int/None | None | DB auth only |
| `username` | str/None | None | DB auth only |
| `current_page` | str | `"board"` | Active page key |
| `property_id` | int/None | None | Selected property scope |
| `selected_turnover_id` | int/None | None | Turnover for unit detail |
| `admin_enable_db_writes` | bool | False | Admin override for writes |
| `board_filters` | dict | `{priority, phase, readiness: "All"}` | Legacy filter state |

**Cross-page coordination keys:**

| Key | Written by | Read by | Behavior |
|-----|-----------|---------|---------|
| `board_filter` | `morning_workflow.py`, `risk_radar.py` | `board.py` | Filters board to breach category; banner + clear button shown |
| `mw_focus_repair_queue` | `morning_workflow.py` | `morning_workflow.py` | One-shot: shows repair queue hint |
| `_validator_access_restricted_notice` | `router.py` | `sidebar.py` | One-shot: access restriction warning |
| `board_info_editor` | Streamlit widget | `board_table.py` | Popped after mutations to reset grid |
| `board_task_editor` | Streamlit widget | `board_table.py` | Not popped (potential stale-state issue) |
| `ai_session_id`, `ai_messages`, `ai_sessions` | `ai_agent.py` | `ai_agent.py` | In-screen init |
| `export_*_bytes` | `export_reports.py` | `export_reports.py` | "Prepare then download" blobs |
| `_admin_app_user_flash` | `admin.py` | `admin.py` | One-shot tuple `(kind, text)` |

---

## 5. Authentication

File: `ui/auth.py`

**Three auth modes controlled by `LEGACY_AUTH_SOURCE` + `AUTH_DISABLED`:**

1. **`AUTH_DISABLED=true`** → `authenticated=True, access_mode="full"` immediately
2. **`LEGACY_AUTH_SOURCE=env`** → compares form input against `APP_*` / `VALIDATOR_*` env vars
   - Validator match → `access_mode="validator_only"`
   - Admin match → `access_mode="full"`
3. **`LEGACY_AUTH_SOURCE=db`** → `auth_service.authenticate()` → sets `user_id`, `username`, `access_mode` from DB

Auth forms rendered inline in main area (not sidebar) when unauthenticated.

---

## 6. Board & Board Table

**Board load flow:**
```
board.py → board_service.get_board()
         → board_reconciliation.run()     # healing: missing turnovers, task backfill
         → lifecycle_transition_service   # automated state transitions
         → repositories
         → domain/priority_engine.py      # sort/score
         → domain/readiness.py            # task completion status
         → returns structured board rows
```

**Filter handling (board.py):**
- `board_filter` passthrough checked first (line 45); blue banner + clear button
- Inline filter bar: search text, phase multiselect, status selectbox, N/V/M, QC, assignee
- All live — selectbox/multiselect rerun on change (no submit button)

**Board table (`ui/components/board_table.py`):**

Two tabs: **Unit Info** and **Unit Tasks**

*Unit Info tab — `st.data_editor` (line 362):*
- Key: `"board_info_editor"` (popped after mutations at line 444)
- 13 columns; 5 editable: Status (`SelectboxColumn`), Move-Out/Ready Date/Move-In (`DateColumn`), QC (`SelectboxColumn`)
- QC column disabled if any row lacks QUALITY_CONTROL task
- `▶` checkbox column navigates to unit detail on toggle

*Unit Tasks tab — `st.data_editor` (line 477):*
- Key: `"board_task_editor"` (NOT popped — potential stale state)
- Dynamic columns: task types present on board, each with a paired `DateColumn`
- 5 frozen read-only columns: Unit, ⚖, Status, DV, DTBR

**Mutation patterns:**
- Collect all changed cells → batch by turnover ID → persist via `turnover_service.update_turnover()` or `task_service.update_task()`
- All writes include `actor="board"` and `source="board_inline_edit"`
- After success: pop editor key, clear `st.cache_data`, call `st.rerun()`

**Duplicate status mapping:** `_board_status_to_db()` in `board_table.py:63` and `_unit_detail_status_to_fields()` in `unit_detail.py:64` are **identical** and must stay in sync.

---

## 7. Unit Detail Screen

File: `ui/screens/unit_detail.py`

**Entry logic:**
- If `selected_turnover_id is None` → render lookup UI (`_render_lookup`)
- Else → render full 7-panel detail view

**Back button** (line 175): pops `selected_turnover_id`, `board_info_editor`, `board_task_editor` → sets `current_page="board"` → `st.rerun()`

**7 panels:**
1. Unit Information — unit code, legal dot (🟢/🔴), legal toggle (on_change autosave), 5-col metadata
2. Status & QC — status selectbox (on_change autosave), QC label, SLA indicator
3. Dates — move-out, ready date, move-in date inputs (all on_change autosave)
4. W/D Status — present selectbox, notified/installed button pairs
5. Risks — open risks list with severity icons
6. Tasks — per-task grid: Task | Assignee | Date | Execution | Completed At | Req | Blocking
7. Notes — note list with resolve buttons + add-note form

**Autosave pattern:**
- `on_change` callbacks read session state, call service, clear cache
- **No `st.rerun()` inside callbacks** — Streamlit triggers rerun post-callback automatically

**Task grid widget keys:** `f"ud_exec_{tid}"`, `f"ud_due_{tid}"`, `f"ud_assignee_{tid}"`, `f"ud_req_{tid}"`, `f"ud_block_{tid}"`, `f"ud_completed_at_{tid}"`

---

## 8. Admin Screen

File: `ui/screens/admin.py` — the control plane.

**DB Writes toggle:**
- Checkbox synced from DB on each run via `get_enable_db_write`
- `on_change` persists via `set_enable_db_write`
- Source of truth: DB (not widget default)

**4 tabs:**
1. Add Turnover — `st.form` → `turnover_service.create_turnover()`
2. Unit Master Import — `st.file_uploader` for Units.csv → `unit_service.import_unit_master()`
3. Phase Manager — multiselect + "Apply" → `scope_service.update_phase_scope()` (affects entire app)
4. App Users — per-user expanders with password update + role change forms; flash via `_admin_app_user_flash`

---

## 9. Key Constants (`ui/state/constants.py`)

**EXEC_MAP** (DB → UI): `NOT_STARTED → "Not Started"`, `SCHEDULED`, `IN_PROGRESS`, `COMPLETED`

**EXEC_REV** (UI → DB): includes extended labels `"N/A"` and `"Canceled"` both mapping to `COMPLETED`

**EXEC_LABELS** (4 basic): `["Not Started", "Scheduled", "In Progress", "Completed"]`

**EXEC_LABELS_EXTENDED** (6, unit detail only): adds `"N/A"`, `"Canceled"`

**EXEC_SIDE_EFFECTS**: N/A → `{required: False}`; Canceled → `{required: False, blocking: False}`

**TASK_COLS** (canonical board column order): `["INSPECT", "CARPET_BID", "MAKE_READY_BID", "PAINT", "MAKE_READY", "HOUSEKEEPING", "CARPET_CLEAN", "FINAL_WALK", "QUALITY_CONTROL"]`

**STATUS_OPTIONS**: `["Vacant ready", "Vacant not ready", "On notice"]`

**BLOCK_OPTIONS**: 7 options including "Not Blocking", "Key Delivery", "Vendor Delay", etc.

---

## 10. Component Inventory

| Artifact | Role | Status |
|----------|------|--------|
| `ui/components/sidebar.py` | Global chrome (nav + property + flags) | Active |
| `ui/components/board_table.py` | Board Unit Info / Unit Tasks tabs + persistence | Active |
| `ui/components/task_panel.py` | Simple task list + Complete button | **Unused** by router screens |
| `ui/components/filters.py` | Filter widget set | **Unused** — board uses inline filter bar |
| `ui/helpers/formatting.py` | All display formatting + color logic | Active |
| `ui/state/constants.py` | Dropdown labels, execution maps, task ordering | Active |
| `ui/state/session.py` | Session state initialization | Active |
| `ui/auth.py` | Auth logic (env + DB + disabled) | Active |
| `ui/router.py` | Page dispatch | Active |

---

## 11. Dead / Parallel Paths

- **`ui/components/filters.py`** — not imported by any live screen; board implements its own inline filter bar
- **`ui/components/task_panel.py`** — appears only in docs copies; not used by live screens
- **`docs/legacy/` and `docs/export_reference/`** — older Streamlit shapes; do not treat as source of truth for migration

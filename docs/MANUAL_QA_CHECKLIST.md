# DMRB Streamlit — Manual QA Checklist

**Scope:** `dmrb/dmrb-legacy` — entrypoint `app.py` → `ui/components/sidebar.py` + `ui/router.py`.

**Findings log (pass / fail / unclear):** Record each issue in **`MANUAL_QA_FINDINGS.md`** using the six-field template there — not in this file.

**Rules for testers:** Every item is **Action** → **Expected result**. Use a property that has realistic turnover data unless testing the empty case.

---

## Testing Pattern (apply to every page)

For **every** screen in **§3 Page-by-page** (below), run this **before** or **alongside** the page-specific checks:

- [ ] Page loads without error
- [ ] All buttons clickable
- [ ] Inputs accept valid values
- [ ] Invalid inputs handled correctly
- [ ] Data displayed matches backend

Page sections below are **page-specific** expectations (navigation, copy, workflows). Do not rely on UI-only checks alone — complete **[§4 Critical Truth Validation](#4-critical-truth-validation-do-not-skip)** every run.

---

## 0. Entry & authentication (`ui/auth.py`)

- [ ] **Action:** Start the app with `LEGACY_AUTH_SOURCE` unset or `env`, and `APP_USERNAME` / `APP_PASSWORD` **unset** (empty), and no validator pair. **Expected:** App loads without a login form; main content appears after sidebar.
- [ ] **Action:** Set both `APP_USERNAME` and `APP_PASSWORD` in environment (or equivalent config). **Expected:** Login form appears; correct credentials set `authenticated` and show main app; wrong credentials show **Invalid username or password.**
- [ ] **Action:** Set `LEGACY_AUTH_SOURCE=db`, run migration/bootstrap, create a user via **Admin → App users** (or CLI `create_app_user.py`). **Expected:** Login form; correct DB user shows full app; wrong password shows **Invalid username or password.** Session has `user_id` / `username`.
- [ ] **Action:** With `LEGACY_AUTH_SOURCE=db` and an empty `app_user` table. **Expected:** Warning about creating a user; login still fails until a row exists.
- [ ] **Action:** Set `AUTH_DISABLED=true` (or `1`). **Expected:** No login form; full access (dev only).

---

## 1. Global UI — sidebar & navigation (`ui/components/sidebar.py`)

### 1.1 Property selector

- [ ] **Action:** With multiple properties in DB, open the **Property** `st.selectbox` and choose a different property. **Expected:** `st.session_state.property_id` updates; screens that use the active property show data for the newly selected property (e.g. board caption **Active Property:** matches).
- [ ] **Action:** Select property A, navigate to a non-default page (e.g. **Morning WF**), then refresh the browser. **Expected:** App reloads; **Property** selection still reflects property A (Streamlit session); page may reset to default session behavior — verify property id is still correct after refresh.

### 1.2 Navigation groups and page keys

Sidebar groups and **exact** button labels → **router page keys** (`ui/router.py`):

| Group | Button label | `current_page` key |
|--------|----------------|-------------------|
| Quick Tools | ➕ Add Turnover | `add_turnover` |
| Quick Tools | 🔍 Unit Lookup | `unit_detail` |
| Quick Tools | 🤖 DMRB AI Agent | `ai_agent` |
| Daily Ops | 🌅 Morning WF | `morning_workflow` |
| Daily Ops | 📋 DMRB Board | `board` |
| Daily Ops | 📅 Ops Schedule | `operations_schedule` |
| Daily Ops | 🚩 Flag Bridge | `flag_bridge` |
| Daily Ops | 📡 Risk Radar | `risk_radar` |
| Daily Ops | 🔧 W/O Validator | `work_order_validator` |
| Import & Reports | 📥 Import Reports | `import_console` |
| Import & Reports | 🛠 Repair Reports | `repair_reports` |
| Import & Reports | Export Reports | `export_reports` |
| Administration | 📥 Report Operations | `import_reports` |
| Administration | 🏗️ Structure | `property_structure` |
| Administration | ⚙️ Admin | `admin` |

- [ ] **Action:** Click each row’s button once. **Expected:** Main area shows the screen for that key (title/content matches section 3 below); the clicked button renders as **primary** (active), others **secondary**.
- [ ] **Action:** From **🔍 Unit Lookup**, click **📋 DMRB Board**, then **🔍 Unit Lookup** again. **Expected:** Navigating away from `unit_detail` clears `selected_turnover_id` (per sidebar code); Unit Lookup shows lookup flow, not a stale turnover.
- [ ] **Action:** Click through several pages in quick succession (e.g. Board → Risk Radar → Board → Flag Bridge). **Expected:** No Python tracebacks; each page matches its screen.

### 1.3 Sidebar expanders

- [ ] **Action:** Collapse and expand each group (**Quick Tools**, **Daily Ops**, **Import & Reports**, **Administration**). **Expected:** Buttons remain reachable; active page button still visible when group is expanded.

### 1.4 Top Flags (sidebar, below navigation)

Categories: **📋 Insp Breach**, **⚠ SLA Breach**, **🔴 MI Danger**, **📅 Plan Breach** — each expander lists up to 5 units (`unit_code · DV …`).

- [ ] **Action:** When the property has flagged units, open each expander. **Expected:** Unit list matches data; **No flagged units** when none qualify.
- [ ] **Action:** Click a unit row button. **Expected:** `selected_turnover_id` is set, `current_page` becomes `unit_detail`, app reruns to **Unit Lookup** detail view for that turnover.

---

## 2. Shared / cross-cutting components

### 2.1 Board filters — **not** `filters.py` on the Board screen

**Note:** `ui/components/filters.py` defines `render_filters()` (Priority / Phase / Readiness + **Apply Filters**) and `apply_filters()`, but **no screen imports it**. The **DMRB Board** uses the inline filter bar in `ui/screens/board.py` instead.

**Board** (`board.py`) filter bar controls:

- **Search unit** (text)
- **Phase** (multiselect; placeholder “All”)
- **Status** — `All`, `Vacant`, plus `STATUS_OPTIONS` from `ui/state/constants.py` (`Vacant ready`, `Vacant not ready`, `On notice`)
- **N/V/M** — `NVM_OPTS`: `All`, `Notice`, `Notice + SMI`, `Vacant`, `SMI`, `Move-In`
- **QC** — `QC_OPTS`: `All`, `QC Done`, `QC Not done`
- **Assignee** — `All` + assignees from board tasks
- Metrics: **Active**, **CRIT**

- [ ] **Action:** Type a substring of a real unit code in **Search unit**. **Expected:** Board table only shows matching units (match on `unit_code_norm`).
- [ ] **Action:** Select one or more **Phase** codes, then clear. **Expected:** With selection, only units in those phases; with none, all phases in scope.
- [ ] **Action:** Set **Status** to each non-All value. **Expected:** Rows match `display_status_for_board_item`; **Vacant** includes both vacant-ready and vacant-not-ready displays.
- [ ] **Action:** Change **N/V/M**, **QC**, **Assignee**. **Expected:** Row set narrows appropriately; **Active** / **CRIT** counts in the filter bar reflect the filtered `board` list.

### 2.2 Flag Bridge passthrough (`board.py`)

- [ ] **Action:** From **Morning WF**, when **SLA Breach** &gt; 0, click **Flag Bridge**. **Expected:** Navigates to **Flag Bridge** with `board_filter` = SLA risk category; board shows info banner and filtered units; **Clear Filter** removes passthrough and restores normal board filtering.

### 2.3 Board table (`ui/components/board_table.py`)

Tabs: **Unit Info** | **Unit Tasks**.

- [ ] **Action:** Switch between **Unit Info** and **Unit Tasks**. **Expected:** Columns match tab (info vs task pipeline columns); same row order/order of units.
- [ ] **Action:** Toggle **▶** on one row in either tab. **Expected:** App sets `selected_turnover_id` and navigates to **`unit_detail`**.
- [ ] **Action:** Edit editable columns (e.g. **Status**, **QC** on Unit Info; task execution columns on Unit Tasks where not disabled). **Expected:** With DB writes enabled, changes persist via `turnover_service.update_turnover` / `task_service.update_task` (source `board_inline_edit`, actor `board`); app clears `st.cache_data` and reruns so the table reflects DB state. With writes disabled, expect `WritesDisabledError` surfaced as `st.error` per row/turnover.

### 2.4 Task panel (`ui/components/task_panel.py`)

Used when embedded (if any screen imports it — verify call sites). **Unit detail** uses `_render_tasks` in `unit_detail.py`, not `task_panel.py` for the main task UI.

- [ ] **Action:** If `render_task_panel` is used anywhere in your branch, click **Complete** on a non-completed task. **Expected:** `task_service.complete_task` runs; after rerun, task shows completed or **Complete** hidden.

---

## 3. Page-by-page (aligned with `ui/router.py`)

Apply the **[Testing Pattern](#testing-pattern-apply-to-every-page)** for each subsection. Subsections below add **screen-specific** actions and expectations.

### 3.1 DMRB Board (`ui/screens/board.py`)

- [ ] **Action:** Open **📋 DMRB Board** with a valid `property_id`. **Expected:** Caption **Active Property:** shows name; metrics row shows **Active Units**, **Violations**, **Plan Breach**, **SLA Breach**, **Move-In Risk**, **Work Stalled**; table shows **Unit Info** / **Unit Tasks** or “No turnovers match filters.”

### 3.2 Unit Lookup / Unit Detail (`ui/screens/unit_detail.py`)

**Lookup** (no `selected_turnover_id`): search + **Go**.

- [ ] **Action:** Enter a valid unit code with an open turnover; click **Go**. **Expected:** Navigates to detail for that turnover.
- [ ] **Action:** Enter unknown code. **Expected:** Warning unit not found.
- [ ] **Action:** Enter unit with no open turnover. **Expected:** Info message — no open turnover.

**Detail** panels: **UNIT INFORMATION**; **Status & QC**; **DATES**; **W/D STATUS**; **RISKS**; expander **Authority & Import Comparison**; **TASKS**; **NOTES**; expander **History**; **TURNOVER ACTIONS** (if `is_open`).

- [ ] **Action:** Click **← Back**. **Expected:** Clears `selected_turnover_id` and board editor keys; `current_page` = `board`.
- [ ] **Action:** Change task **Assignee**, **Date**, **Execution**, **Req**, **Blocking** (widgets with `on_change` / `_persist_task_update`). **Expected:** With DB writes enabled, updates persist; with writes disabled, **Database writes are currently disabled.**
- [ ] **Action:** Add a note (text + severity) and **Add note**. **Expected:** New note appears; **Resolve** resolves an open note.
- [ ] **Action:** Open **History** expander. **Expected:** Audit dataframe shows entries when history exists.
- [ ] **Action:** For open turnover, **Cancel Turnover**. **Expected:** Turnover cancels per service rules; navigation back to board on success.

### 3.3 Add Turnover (`ui/screens/add_turnover.py`)

- [ ] **Action:** Click **← Back to Board**. **Expected:** `current_page` = `board`.
- [ ] **Action:** Select Phase → Building → Unit; submit **Create Turnover** with valid dates. **Expected:** Success message with turnover id; navigates to `unit_detail` with `selected_turnover_id` set.
- [ ] **Action:** Submit when service raises `TurnoverError`. **Expected:** `st.warning` with message (e.g. duplicate open turnover).

### 3.4 Morning Workflow (`ui/screens/morning_workflow.py`)

Sections: import status metrics (**Move-Out**, **Move-In**, **Available**, **FAS**); risk metrics (**Vacant > 7 days**, **SLA Breach**, **Move-In ≤ 3 days**); **Flag Bridge** / **Open Board** buttons; **Missing Move-Out** table (if rows); **Today's Critical Units** table.

- [ ] **Action:** Verify import timestamp metrics show datetime or **—** / **Not imported** caption.
- [ ] **Action:** Click **Open Board**. **Expected:** `current_page` = `board`.
- [ ] **Action:** If missing move-out rows exist, enter **Move-Out** date in editor. **Expected:** Turnover creation runs; success messages; cache clear + rerun on creation.
- [ ] **Action:** Toggle **▶** on a critical unit row. **Expected:** Navigate to `unit_detail`.

### 3.5 Operations Schedule (`ui/screens/operations_schedule.py`)

Title **📅 Operations Schedule**. Tabs: **Manager View** | **Vendor View**.

- [ ] **Action:** In **Manager View**, change **Filter by task type** multiselect. **Expected:** Table only shows selected types.
- [ ] **Action:** Edit **Date**, **Assignee**, **Status**; click **Save Changes**. **Expected:** Updated task count success or **No changes detected** / per-row errors.
- [ ] **Action:** Open **Vendor View**. **Expected:** Read-only dataframe of Date, Unit, Task, Assignee, Status.

### 3.6 Flag Bridge (`ui/screens/flag_bridge.py`)

Filters: **Phase**, **Status**, **N/V/M**, **Assignee**, **Flag Bridge** (`BRIDGE_OPTS`), **Value**. Metrics: **Total Units**, **Violations**, **Units w/ Breach**. Breach table with **▶** navigation.

- [ ] **Action:** Apply **Flag Bridge** dropdown (e.g. **Insp Breach**, **SLA Breach**). **Expected:** Row set matches filter logic.
- [ ] **Action:** Toggle **▶** on a row. **Expected:** Opens `unit_detail` for that turnover.

### 3.7 Risk Radar (`ui/screens/risk_radar.py`)

Subheader **Turnover Risk Radar**. Filters: **Phase**, **Risk Level** (`All` / HIGH / MEDIUM / LOW), **Unit Search**. Metrics: **Total Active Turnovers**, **High Risk**, **Medium Risk**, **Low Risk**. Read-only table (Unit, Phase, Risk Level, Risk Score, Risk Reasons, Move-in Date).

- [ ] **Action:** Confirm rows are ordered by **Risk Score** descending (code sorts before display).
- [ ] **Action:** Filter by **Risk Level** and **Unit Search**. **Expected:** Subset matches filters; empty state message when none.

### 3.8 Import Reports — Import Console (`ui/screens/import_console.py`)

**Note:** Sidebar label **📥 Import Reports** routes here (`import_console`). Title: **Import Reports**.

**IMPORT CONSOLE** sub-tabs: **Available Units**, **Move Outs**, **Pending Move-Ins**, **Final Account Statement (FAS)**.

Per sub-tab: file uploader (`csv`/`xlsx`), **Run \<label\> import** button, latest batch caption, full rows table, clean table; **CONFLICTS** section (placeholder caption).

- [ ] **Action:** Run import with **no file**. **Expected:** **Upload a file first.**
- [ ] **Action:** Run valid import. **Expected:** Success / duplicate / error paths per `import_service.run_import_pipeline` messages; `st.cache_data.clear()` + rerun on success path.
- [ ] **Action:** On **Available Units** tab, read the caption under the clean table (on-notice / vacant-not-ready behavior). **Expected:** Copy explains board-time behavior; there is **no** separate “Apply latest …” button on this screen (readiness is applied via import pipeline + board reconciliation, not a manual stub).

### 3.9 Report Operations (`ui/screens/import_reports.py`)

Sidebar: **Administration → 📥 Report Operations**. Title **Report Operations**. Tabs: **Override Conflicts** | **Invalid Data** | **Import Diagnostics**.

- [ ] **Action:** **Override Conflicts:** for each row, **Keep Manual** or **Accept Report**. **Expected:** Success message, row updates, rerun.
- [ ] **Action:** **Invalid Data:** expand row, set **Corrected date**, **Apply Correction**. **Expected:** Resolution or validation error message.
- [ ] **Action:** **Import Diagnostics:** review batch table; choose **Inspect batch**; **Expected:** Row detail table or empty message.

### 3.10 Repair Reports (`ui/screens/repair_reports.py`)

Tabs: **Missing Move-Out** | **FAS Tracker** (uses `render_missing_move_out` / `render_fas_tracker` from `import_reports.py`).

- [ ] **Action:** **Missing Move-Out:** enter move-out date where applicable. **Expected:** Turnover created via `missing_move_out_service.resolve_missing_move_out` path; success + rerun.
- [ ] **Action:** **FAS Tracker:** edit **Note**; **Save Changes**. **Expected:** Saved count or **No changes detected.**

### 3.11 Export Reports (`ui/screens/export_reports.py`)

**EXPORT CONSOLE:** **Prepare Export Files**. **DOWNLOADS** tabs: **Excel reports** | **Summary & chart** | **Full package**.

- [ ] **Action:** Click **Prepare Export Files**. **Expected:** On success, session holds bytes; caption shows last prepare date and turnover count; on failure, **export_prepare_error** message and downloads empty.
- [ ] **Action:** Download **Final Report (XLSX)**, **DMRB Report (XLSX)**, **Weekly Summary (TXT)**, **Dashboard Chart (PNG)**, **All Reports (ZIP)**. **Expected:** Files open without corruption; sizes non-zero after successful prepare.

### 3.12 Work Order Validator (`ui/screens/work_order_validator.py`)

**HISTORICAL MOVINGS IMPORT:** upload + **Load Historical Movings**. **WORK ORDER VALIDATOR:** upload + **Validate Work Orders**.

- [ ] **Action:** Run **Load Historical Movings** without file. **Expected:** **Upload a file first.**
- [ ] **Action:** Run **Validate Work Orders** with file missing `unit_number` or `created_date`. **Expected:** Error listing required columns.
- [ ] **Action:** Valid file. **Expected:** Dataframe shows **Make Ready** and **Moving** columns; **Download Validated Work Orders (XLSX)** downloads.

### 3.13 DMRB AI Agent (`ui/screens/ai_agent.py`)

- [ ] **Action:** With no `OPENAI_API_KEY`. **Expected:** Warning referencing secrets / `docs/legacy/AI_AGENT_OPENAI.md`.
- [ ] **Action:** **+ New Chat**. **Expected:** Clears messages.
- [ ] **Action:** Click a suggestion card. **Expected:** Spinner; assistant reply appended when API succeeds; errors on `AiAgentConfigError` / `AiAgentApiError`.
- [ ] **Action:** Type in **Ask anything about turnovers...** and send. **Expected:** Same as above.
- [ ] **Action:** Delete session (**🗑**). **Expected:** Session removed from list.

### 3.14 Admin (`ui/screens/admin.py`)

Control bar: **Enable DB Writes** (synced with `system_settings_service`), **Active Property**, **New Property** + **Create Property**. Tabs: **Add Turnover** | **Unit Master Import** | **Phase Manager** | **App users**.

- [ ] **Action:** Toggle **Enable DB Writes**. **Expected:** `system_settings_service.set_enable_db_write` reflects; caption when off warns writes disabled.
- [ ] **Action:** **Create Property** with non-empty name. **Expected:** New property; `property_id` session updated; appears in sidebar Property list.
- [ ] **Action:** **Add Turnover** tab — same cascade as standalone add turnover; **Add Turnover** form respects write guard.
- [ ] **Action:** **Unit Master Import** — upload **Units.csv**, **Run Unit Master Import**. **Expected:** Created/skipped/errors summary per `unit_service.import_unit_master`.
- [ ] **Action:** **Phase Manager** — **Apply Phase Scope**. **Expected:** Scope updates; board visibility changes for excluded phases.
- [ ] **Action:** **App users** tab — with DB writes on, **Create user** (username, password, role). **Expected:** Row appears in table; `LEGACY_AUTH_SOURCE=db` login works with that user. **Update password** / **Save role** / **Deactivate** behave as expected; write guard blocks when DB writes off.

### 3.15 Property Structure (`ui/screens/property_structure.py`)

Tabs: **Structure** | **Turnovers**.

- [ ] **Action:** **Structure** — expand phase/building expanders. **Expected:** Unit rows show **unit_code_norm**, Active, Carpet, W/D.
- [ ] **Action:** **Turnovers** — **Expected:** Table from `board_service.get_board_view` with columns Unit, Active, Carpet, W/D, Status, DV, DTBR, QC; or info when no turnovers.

---

## 4. Critical Truth Validation (DO NOT SKIP)

These checks validate that the system is **correct**, not just working. **This section matters more than dozens of shallow UI checks.** 👉 This is where bugs actually hide.

- [ ] **Add a turnover** → verify it appears on **Board** AND counts update correctly
- [ ] **Complete a task** → verify:
  - Task status changes
  - Board metrics update (if applicable)
- [ ] **Create multiple turnovers** → verify:
  - Active count matches actual rows
- [ ] **Trigger SLA breach scenario** → verify:
  - Appears in **Flag Bridge**
  - Count matches Board metrics
- [ ] **Run export** → verify:
  - Export row count = board row count
  - Sample **3 units** → data matches UI exactly

*Also compare **Active Units** / **CRIT** / Morning WF **SLA Breach** to Board and Flag Bridge where applicable — see `board.py` and shared services for definitions.*

---

## 5. Edge cases & stress

- [ ] **Action:** Select a property with **no phases / no units** where applicable. **Expected:** Graceful **st.info** / **st.warning** on Add Turnover, Import Console, etc. — no uncaught exceptions.
- [ ] **Action:** Property with **no open turnovers**. **Expected:** Board shows empty or info; Export **Prepare** may still run depending on `get_board` — verify message and downloads.
- [ ] **Action:** Rapidly click navigation buttons and **▶** checkboxes. **Expected:** No duplicate navigation loops; Streamlit reruns complete.

---

## 6. `filters.py` (optional / technical)

- [ ] **Action:** Confirm whether `render_filters` from `ui/components/filters.py` should be mounted on any page. **Expected:** If product requires Priority/Phase/Readiness + **Apply Filters**, wire it; otherwise document as unused.

---

## 7. After the first full pass (don’t skip ahead)

Once you have run this checklist **end-to-end** once, the next leverage step is to convert scenarios → **automated tests** (e.g. **Playwright** against Streamlit, or **service-level** tests hitting `board_service` / export paths). That turns repeated effort into regression signal.

---

*Generated from repository structure: `sidebar.py`, `router.py`, and screen modules under `ui/screens/`.*

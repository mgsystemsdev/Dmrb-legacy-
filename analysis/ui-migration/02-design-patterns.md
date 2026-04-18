# DMRB Legacy — Extracted Design Patterns & System Rules

> Grounded in live `app.py` + `ui/` codebase. Analysis date: 2026-04-17

---

## Pattern 1: Session-String Router

**What it is:** Navigation is a string stored in `st.session_state["current_page"]`. There are no URL paths.

**Rules:**
- All page keys are `snake_case` strings aligned with `_NAV_GROUPS` in `sidebar.py`
- Default page: `"board"`
- Navigation always uses: set key → (optionally clear `selected_turnover_id`) → `st.rerun()`
- `router.py` uses lazy imports per screen to reduce per-rerun cost

**System rule:** Any new screen must be registered in both `router.py` (dispatch) and `sidebar.py` (`_NAV_GROUPS`). No central route registry exists — discoverability is grep-driven.

---

## Pattern 2: Property-Scoped World

**What it is:** Almost every screen checks `st.session_state.property_id` on entry. Wrong or missing scope = wrong data.

**Rules:**
- If `property_id is None`, screens return early with `st.info()` / `st.warning()` (wording varies by screen)
- `st.caption()` with active property name appears at top of most screens
- Property selector lives exclusively in the sidebar
- All service calls pass `property_id` as a required parameter

**System rule:** No screen should ever render operational data without first asserting `property_id is not None`.

---

## Pattern 3: Phase Scope Filter

**What it is:** `scope_service.get_phase_scope()` returns a tuple of active phase IDs that filters board, schedule, morning workflow, and sidebar flags.

**Rules:**
- Phase scope is stored in DB, not session state
- Admin screen "Phase Manager" tab owns writes via `scope_service.update_phase_scope()`
- Phase scope changes affect the entire app for all users of that property
- Caption on Phase Manager documents this global effect

---

## Pattern 4: Data-Editor Diff-and-Save

**What it is:** `st.data_editor` is the core inline-edit primitive. Every rerun, the original df is compared against the edited df. If mutations exist, they are persisted, the widget key is popped, cache is cleared, and rerun is triggered.

**Rules:**
- Mutations collected by comparing `original_rows[i][field]` vs `edited_rows[i][field]`
- Row identity via a stable `tid_list` aligned with DataFrame row index (fragile — sort/filter breaks this)
- After save: `st.session_state.pop(editor_key, None)` → `st.cache_data.clear()` → `st.rerun()`
- Widget keys for board: `"board_info_editor"` (popped after mutations), `"board_task_editor"` (not popped — known gap)

**System rule:** Never rely on DataFrame row index alone for mutation identity. Use a stable `turnover_id` / `task_id` key column.

---

## Pattern 5: On-Change Autosave

**What it is:** Unit detail uses `on_change` callbacks on individual widgets (selectbox, date_input, toggle) that immediately call the service layer without an explicit save button.

**Rules:**
- Callback reads widget value from `st.session_state[widget_key]`
- Calls service → clears `st.cache_data`
- **No `st.rerun()` inside callbacks** — Streamlit triggers rerun automatically post-callback
- All writes include `actor="manager"` and `source="unit_detail_autosave"`

**System rule:** Widget `on_change` callbacks must not call `st.rerun()`. Rerun inside callback causes double-rerun and stale state.

---

## Pattern 6: Prepare-Then-Download

**What it is:** Export reports uses a two-step flow: first "Prepare Export Files" button generates all blobs and stores them in session state; then download buttons read from session state.

**Rules:**
- Byte blobs keyed: `weekly_summary_bytes`, `final_report_bytes`, `dmrb_report_bytes`, `chart_bytes`, `zip_bytes`
- Error stored in `export_prepare_error` (persistent state, not one-shot)
- Download buttons are always rendered; disabled/empty if bytes not yet prepared
- All prep happens synchronously in one click handler

**System rule:** Large binary prep must complete before user can download. No progress indication exists.

---

## Pattern 7: One-Shot Flash Messages

**What it is:** Session keys used as one-shot notifications that are immediately popped on read.

**Pattern:**
```python
# Write (e.g., in form submit):
st.session_state._admin_app_user_flash = ("success", "User created.")

# Read (at top of render function):
flash = st.session_state.pop("_admin_app_user_flash", None)
if flash:
    kind, text = flash
    (st.success if kind == "success" else st.error)(text)
```

**Keys using this pattern:**
- `_admin_app_user_flash` — admin user operations
- `_validator_access_restricted_notice` — router access denial
- `mw_focus_repair_queue` — morning workflow repair queue focus hint

**System rule:** One-shot keys must be `pop()`-ed on read, not `get()`-ed. Using `get()` causes them to persist across reruns.

---

## Pattern 8: Board-Filter Passthrough

**What it is:** Morning Workflow and Risk Radar set `board_filter` in session state, then navigate to Board. Board reads and applies it as a pre-filter over the full board, showing a banner with a clear button.

**Rules:**
- `board_filter` values: `"SLA_RISK"`, `"MOVE_IN_DANGER"`, `"INSPECTION_DELAY"`, `"PLAN_BREACH"`
- Board checks `st.session_state.get("board_filter")` before rendering filter bar
- Blue info banner: "Showing **{label}** units only"
- Clear button: `st.session_state.pop("board_filter", None)` + rerun

**System rule:** Any screen that wants to pre-filter the board sets `board_filter` + `current_page = "board"` + rerun. The board screen must always check and honor this key.

---

## Pattern 9: Role-Based Gate

**What it is:** Two access modes enforce different UI behavior globally.

| `access_mode` | Sidebar | Router | Screens |
|---------------|---------|--------|---------|
| `"full"` | Full nav + flags | All pages accessible | All features |
| `"validator_only"` | Only W/O Validator button | Forced to `work_order_validator` | Only validator screen |

**Rules:**
- Role check is enforced in both sidebar (`validator_only` branch) and router (`_validator_access_restricted_notice` + forced page)
- DB auth resolves `access_mode` from `app_user.role`; env auth uses presence of `VALIDATOR_*` credentials

---

## Pattern 10: Widget Key Reset Strategy

**What it is:** To force Streamlit to re-render a widget with fresh data, the widget key is deleted from session state, causing Streamlit to reinitialize it on next rerun.

**Instances:**
- `board_info_editor` popped at `board_table.py:444` after mutations
- `selected_turnover_id`, `board_info_editor`, `board_task_editor` all popped in unit_detail back button (lines 176-178)
- Same three keys popped in Cancel Turnover action (lines 361-363)

**System rule:** Any widget that must reset to show updated data (not Streamlit's cached pre-edit state) must have its session key deleted before or after the mutation that changes its data.

---

## Pattern 11: Row-Select Navigation (▶ Checkbox)

**What it is:** `st.data_editor` grids include a `▶ CheckboxColumn`. Toggling any row navigates to that turnover's unit detail.

**Used in:** Board (both tabs), Flag Bridge

**Mechanics:**
```python
# After st.data_editor returns edited df:
selected = edited[edited["▶"] == True]
if not selected.empty:
    idx = selected.index[0]
    st.session_state.selected_turnover_id = tid_list[idx]
    st.session_state.current_page = "unit_detail"
    st.rerun()
```

**System rule:** `tid_list` (list of `turnover_id` values aligned with df row index) must be passed alongside the df to resolve row → entity mapping.

---

## Pattern 12: Dynamic Column Injection

**What it is:** The board's Unit Tasks tab discovers which task types are present in the current board rows and builds columns dynamically, merged with the canonical `TASK_COLS` order.

**Rules:**
- `TASK_COLS` defines the canonical order (from `ui/state/constants.py`)
- Extra task types not in `TASK_COLS` are appended in discovery order
- Each task column gets a paired ` Date` column
- Column config built dynamically: `SelectboxColumn` for status, `DateColumn` for due dates

---

## Pattern 13: QC Guard

**What it is:** If any row on the board lacks a QUALITY_CONTROL task, the QC column is disabled for all rows (with an explanatory caption).

**Rule:** `_board_any_turnover_missing_qc_task()` runs on every board render. If True, QC column is added to `disabled` list in `st.data_editor`.

---

## Pattern 14: Manager vs Vendor View Split

**What it is:** Operations Schedule shows different UIs based on role.

| View | Widget | Editable Columns | Save Method |
|------|--------|-----------------|-------------|
| Manager | `st.data_editor` | Date, Assignee, Status | "Save Changes" button → batch update |
| Vendor | `st.dataframe` | None (read-only) | N/A |

**Rule:** Manager = `st.data_editor` with explicit save; Vendor = `st.dataframe` read-only. Role determined from session `access_mode`.

---

## Pattern 15: Service Call Conventions

All service calls from render functions include metadata:
- `actor` — who triggered (e.g., `"board"`, `"manager"`, `"admin"`)
- `source` — UI location (e.g., `"board_inline_edit"`, `"unit_detail_autosave"`)
- `WritesDisabledError` raised by services when DB writes toggle is OFF; screens display `st.warning()`

---

## Pattern 16: Cache + Rerun Cycle

**Standard mutation → refresh cycle:**
1. Call service to persist change
2. `st.cache_data.clear()` — coarse invalidation of all `@st.cache_data` caches
3. (Optionally pop widget key)
4. `st.rerun()` — triggers full script rerun with fresh data

**Cache TTL:** Most board/service caches use 30-second TTL (`@st.cache_data(ttl=30)`). Admin operations clear immediately.

---

## Pattern 17: Emoji as Icon System

The app uses emoji extensively as a substitute for an icon system:

| Context | Emoji | Meaning |
|---------|-------|---------|
| Nav groups | ➕🔍🤖🌅📋📅🚩📡🔧📥🛠⚙️🏗️ | Page destinations |
| Risk levels | 🔴🟠🟢 | HIGH / MEDIUM / LOW |
| Priority | 🔴🟠🟡🔵⚪ | MOVE_IN_DANGER / SLA_RISK / INSPECTION_DELAY / NORMAL / LOW |
| Readiness | ✅🚫🔄⬜➖ | READY / BLOCKED / IN_PROGRESS / NOT_STARTED / NO_TASKS |
| SLA | ✅⚠️🚨 | OK / WARNING / BREACH |
| Carpet | 🟢⚪🔶 | Carpet / No Carpet / Replacement |
| Notes | ℹ️⚠️🚨 | INFO / WARNING / CRITICAL |
| Board ▶ | ▶ (Unicode) | Navigate to unit detail |

**System rule:** Emoji are used as both data encodings (risk level) and navigation affordances (▶). Any migration must map these to accessible equivalents.

---

## Pattern 18: Formatting Conventions

From `ui/helpers/formatting.py`:

| Format Function | Output | Special Logic |
|-----------------|--------|---------------|
| `format_date` | ISO date or "—" | None |
| `format_dv` | "Xd" or `:red[**Xd**]` | Red if > threshold (default 10) |
| `board_breach_row_display` | BoardBreachDisplay dataclass | Multi-source breach detection (agreements first, then priority/SLA/readiness fallback) |
| `display_status_for_board_item` | Status string | Uses `effective_manual_ready_status` when present, else lifecycle phase label |

**Streamlit-specific:** `:red[...]`, `:orange[...]` shorthand used for inline color in text. These are Streamlit-only syntax.

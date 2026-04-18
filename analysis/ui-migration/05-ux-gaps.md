# DMRB Legacy — UX Gaps & Improvement Opportunities

> Analysis of issues in the current Streamlit implementation and recommendations for the migration target.
> Analysis date: 2026-04-17

---

## Critical Gaps (must fix in migration)

### 1. No Real URLs — Zero Shareability

**Issue:** All navigation is session-string based (`current_page` key). There are no URL paths for pages or individual turnovers.

**Impact:** Operators and support cannot share links. Refreshing the page resets to board. Browser back/forward don't work. Deep linking to a specific unit detail is impossible.

**Fix in migration:**
- Introduce real URL routes: `/properties/{pid}/board`, `/turnovers/{tid}`, `/admin/...`
- `selected_turnover_id` becomes a URL path parameter: `/turnovers/1234`
- `board_filter` becomes a query parameter: `/board?filter=SLA_RISK`

---

### 2. Fragile Row-Identity in Data Grids

**Issue:** Both board tabs use DataFrame row index aligned with a parallel `tid_list`. If sort order changes during a rerun, the index mapping breaks, causing mutations to be applied to the wrong turnover.

**Impact:** Potential data corruption under certain sort/filter state changes between the request that loaded the data and the request that saves mutations.

**Fix in migration:**
- Always use `turnover_id` / `task_id` as explicit row key in grids (AG Grid `getRowId`, TanStack Table `getRowId`)
- Never rely on implicit positional alignment between server data and grid row index

---

### 3. `board_task_editor` Not Reset After Mutations

**Issue:** `board_info_editor` is popped from session state after mutations (correct), but `board_task_editor` is not. This means after saving task changes, the grid may show stale pre-edit state on next rerun until something else clears it.

**Fix in current codebase:** Pop `board_task_editor` at `board_table.py:566` (after task mutations, same as line 444 for info tab).

**Fix in migration:** Grid libraries have proper dirty-state APIs; this issue doesn't apply in non-Streamlit frameworks.

---

### 4. Coarse Cache Invalidation

**Issue:** `st.cache_data.clear()` clears ALL caches globally after any mutation. This is simple but causes unnecessary re-fetches of unrelated data.

**Impact:** Performance degradation at scale; forces full board reload even for single-field updates.

**Fix in migration:** Fine-grained cache invalidation by entity type (e.g., `queryClient.invalidateQueries(["board", propertyId])` after a board mutation, not global clear).

---

### 5. No Progress Indication on Long Operations

**Issue:** Unit master CSV import and export file preparation run synchronously. No spinner, progress bar, or status feedback during execution. Large CSVs or complex boards silently block the UI.

**Fix in migration:**
- Background tasks for imports and exports
- SSE or polling for progress
- "Preparing..." spinner at minimum

---

### 6. Status/QC Mapping Duplicated in Two Files

**Issue:** `_board_status_to_db()` in `board_table.py:63` and `_unit_detail_status_to_fields()` in `unit_detail.py:64` are functionally identical. If one is updated and the other isn't, board and unit detail will diverge silently.

**Fix in migration:** Centralize in a single service layer function or constants module. Single source of truth.

---

### 7. Prepare-Then-Download is Synchronous & Memory-Unsafe

**Issue:** Export blobs (`final_report_bytes`, `zip_bytes`, etc.) are generated synchronously in one click and held in session state as raw bytes. On busy boards, ZIP generation can take seconds. Session memory grows per export attempt.

**Fix in migration:**
- Generate exports as background tasks
- Store to temp files or object storage
- Return download URLs (stream or signed URL)
- Progressive download when ready

---

## Significant UX Problems

### 8. ▶ Checkbox is a Confusing Navigation Affordance

**Issue:** Using a checkbox to navigate to a different page is unexpected UX. Users expect checkboxes to select rows for batch operations, not to open detail views.

**Impact:** New users can't discover navigation. No tooltip or obvious visual affordance.

**Improvement:** Replace with an explicit "View" link/button column in the grid. Or a clickable row with clear hover affordance. Keep ▶ only if user research confirms familiarity.

---

### 9. Filter UX Inconsistency

**Issue:** Board uses a live inline filter bar (no submit). `ui/components/filters.py` defines a filter component but is not used by any live screen. Operations Schedule uses a task type multiselect inline. There is no consistent filter pattern across screens.

**Impact:** Users must learn different filter models per screen. Dead code (`filters.py`) creates confusion.

**Fix in migration:** Decide on one filter pattern (live OR submit-on-apply) and apply it consistently. Delete or implement `filters.py`.

---

### 10. Emoji-Only Status Encoding

**Issue:** Risk levels (`🔴🟠🟢`), readiness (`✅🚫🔄⬜➖`), and SLA (`✅⚠️🚨`) are encoded only as emoji. No text label for screen readers or color-blind users.

**Impact:** Not accessible. Screen readers announce "🔴" not "HIGH risk". Color-blind users may misread traffic-light signals.

**Fix in migration:** Use text labels with optional emoji prefix: "🔴 HIGH", "🟠 MEDIUM". Add CSS class for color (not emoji alone). Map `format_dv`'s `:red[...]` to CSS class `text-red-600` with visible label.

---

### 11. No Concurrent Edit Protection

**Issue:** Two managers editing the same board simultaneously will silently overwrite each other's changes. The last save wins with no conflict detection.

**Impact:** Data loss under concurrent use.

**Fix in migration:** Optimistic locking via `updated_at` timestamp check (ETags). Reject conflicting writes with `409 Conflict`. UI shows "This record was changed by another user — reload?"

---

### 12. Autosave Has No Visual Confirmation

**Issue:** Unit detail's `on_change` autosave is silent. Users cannot confirm their change was saved. No "Saving..." indicator, no "Saved ✓" feedback.

**Impact:** Operators may re-enter data they already saved, or doubt whether changes took.

**Fix in migration:** Show a brief "Saved" toast/badge after each autosave. Show "Saving..." during the async call.

---

### 13. AI Agent Has No Session Persistence

**Issue:** `ai_messages` and `ai_session_id` are stored in Streamlit session state (ephemeral). Refreshing the page or navigating away loses conversation history.

**Impact:** Operators lose context when they switch screens.

**Fix in migration:**
- Persist AI sessions server-side (DB table or Redis)
- Load history on mount
- Allow named sessions

---

### 14. Export Reports: "Prepare" Must Be Re-Run on Every Load

**Issue:** Export bytes are lost on page refresh (session state). Operators must re-click "Prepare" after any navigation away from the export screen.

**Fix in migration:** Queue export jobs server-side. Show list of recent exports with download links. Don't require re-preparation.

---

### 15. Admin Phase Scope Has No Confirmation Step

**Issue:** Clicking "Apply" in Phase Manager immediately changes scope for all users of the property with no confirmation dialog.

**Impact:** Accidental scope changes affect live operations.

**Fix in migration:** Confirmation modal: "This will change phase scope for all users of [property name]. Continue?"

---

## Minor Polish Opportunities

### 16. Inconsistent "Select a Property" Messaging

Different screens use different wording for the null-property guard: `st.info(...)`, `st.warning(...)`, varying messages. These should be standardized.

### 17. Session State Initialization Is Flat

All session keys share one flat dict. In a larger app, collisions between screen-specific keys (e.g., two screens both using `"filter"`) cause subtle bugs.

**Fix:** Namespace keys by screen: `"board.filter"`, `"unit_detail.turnover_id"`.

### 18. `format_dv` Uses Streamlit Markup Inline

`":red[**Xd**]"` is Streamlit-specific syntax embedded in a helper function. This leaks Streamlit-specific rendering into the domain layer.

**Fix in migration:** Return structured data (value, threshold_exceeded: bool). Let the presentation layer decide color.

### 19. Notes and Audit Are Always-Loaded

`_render_notes()` and `_render_audit()` are called on every unit detail load even if the user never opens them (they're in expanders). On turnovers with long history, this adds unnecessary DB queries.

**Fix in migration:** Lazy-load notes and audit via separate API calls triggered when expander opens.

### 20. No Keyboard Navigation

Dense grid tables have no keyboard navigation or focus management. Accessibility for keyboard-only operators is poor.

**Fix in migration:** Use grid libraries with built-in keyboard navigation. Ensure tab order is logical.

---

## Summary Priority Matrix

| Gap | Severity | Effort to Fix | Fix In Migration? |
|-----|----------|--------------|-------------------|
| No real URLs | Critical | Low (routing change) | Yes |
| Fragile row identity | Critical | Medium | Yes |
| board_task_editor not reset | High | Trivial in current codebase | Fix now + migration |
| Coarse cache invalidation | High | Medium | Yes |
| Long ops no progress | High | Medium | Yes |
| Duplicate status mapping | High | Low | Yes |
| Binary export in session | High | Medium | Yes |
| ▶ checkbox navigation | Medium | Low | Yes |
| Filter inconsistency | Medium | Low | Yes |
| Emoji-only status | Medium | Low | Yes |
| No concurrent edit protection | Medium | High | Yes |
| Autosave no visual feedback | Medium | Low | Yes |
| AI session not persisted | Medium | Medium | Yes |
| Export not persisted | Medium | Medium | Yes |
| Phase scope no confirmation | Low | Low | Yes |

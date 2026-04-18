# Phase 1 legacy — static trust verification (dmrb-20260329-A2)

**Date:** 2026-03-30  
**Scope:** Code and documentation review only. This is **not** a substitute for interactive runs in `MANUAL_QA_CHECKLIST.md`, especially **§4 Critical Truth Validation**.

## What was verified without a browser

| Trust theme | Evidence | Result |
|-------------|----------|--------|
| **Board inline save** | `ui/components/board_table.py`: `_render_info_tab` / `_render_tasks_tab` diff edited vs original DataFrame → `_apply_info_tab_mutations` / `_apply_task_tab_mutations` → `turnover_service.update_turnover` (source `board_inline_edit`) and `task_service.update_task` (actor `board`). On success: `st.cache_data.clear()` + `st.rerun()`. | **Pass** (persistence wired) |
| **Unit detail autosave** | `ui/screens/unit_detail.py`: `_autosave_turnover_after_attempt` → `turnover_service.update_turnover` with `source=unit_detail_autosave`; task widgets use `_persist_task_update` / `on_change` callbacks. Legal toggle uses single `update_turnover` with `legal_confirmed_at` + `legal_confirmation_source`. | **Pass** |
| **Import console** | `ui/screens/import_console.py`: upload + `import_service.run_import_pipeline`; success path clears cache and reruns; history captions and row tables from `import_service`. No dead “Apply latest …” button in production screen (see checklist note). | **Pass** |
| **Admin** | `ui/screens/admin.py`: DB writes toggle via `system_settings_service`; property creation, tabs for turnover / unit import / phase scope / app users call real services. | **Pass** (code path) |
| **No fake UI in shipped screens** | Production screens under `ui/screens/*.py` call services/repos; skeleton placeholders live under `docs/legacy/screens/` only (not routed). | **Pass** (routing uses `ui/router.py` → real screens) |

## Automated tests (informational)

`python3 -m pytest tests/` in `dmrb-legacy` reported **22 failed, 214 passed** in this environment (fixture/DB state and a few expectations — e.g. inactive unit, duplicate task types). Failures are **not** introduced by this verification pass. Use a clean test DB or CI matrix before treating pytest green as release gate.

## Required before formal product sign-off

1. Run **`docs/MANUAL_QA_CHECKLIST.md`** end-to-end with a real property and **§4 Critical Truth Validation**.  
2. Log any issues in **`docs/MANUAL_QA_FINDINGS.md`** using the six-field template.

---

*Task: `dmrb-20260329-A2` — static portion closed in repo; interactive sign-off remains with the operator.*

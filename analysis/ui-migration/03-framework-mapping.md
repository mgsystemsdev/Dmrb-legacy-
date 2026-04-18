# DMRB Legacy — Streamlit → Framework Mapping

> Maps each Streamlit pattern to its equivalent in FastAPI+Jinja2+HTMX, Flask+Jinja2+HTMX, and React+Tailwind.
> Analysis date: 2026-04-17

---

## Core Navigation

| Streamlit | FastAPI+Jinja2+HTMX | Flask+Jinja2+HTMX | React+Tailwind |
|-----------|--------------------|--------------------|----------------|
| `st.session_state["current_page"]` string | `request.session["current_page"]` or URL path `/board`, `/unit/{id}` | `session["current_page"]` or Blueprint routes | React Router `<Routes>` with paths |
| `st.rerun()` after nav | `redirect(url_for("board"))` or HTMX `HX-Redirect` header | `redirect(url_for("board"))` | `navigate("/board")` |
| `st.stop()` on auth fail | `return RedirectResponse("/login")` or `raise HTTPException(401)` | `return redirect(url_for("login"))` | Auth guard component → `<Navigate to="/login">` |
| Lazy screen imports | Blueprint registration | Blueprint registration | Route-level code splitting (`React.lazy`) |
| Default page `"board"` | Redirect from `/` to `/board` | Redirect from `/` to `/board` | `<Navigate to="/board">` from `/` |

**Migration note:** Introduce real URLs (`/properties/{pid}/board`, `/turnovers/{tid}`, `/admin/...`) to enable bookmarking, deep linking, and support debugging.

---

## Sidebar & Global Navigation

| Streamlit | FastAPI+Jinja2+HTMX | Flask+Jinja2+HTMX | React+Tailwind |
|-----------|--------------------|--------------------|----------------|
| `ui/components/sidebar.py` | `templates/partials/sidebar.html` | `templates/partials/sidebar.html` | `<Sidebar>` component |
| `st.selectbox` (property) | `<select>` with `hx-post="/set-property"` | `<select>` + form POST + session | `<PropertySelector>` + Context Provider |
| Expander nav groups | `<details>/<summary>` | `<details>/<summary>` | Accordion / `<NavGroup>` |
| `st.button` (nav) | `<a href="...">` styled as button | `<a href="...">` | `<NavLink>` |
| `type="primary"` on active page | CSS `.active` class on current route | CSS `.active` class | `isActive` prop on NavLink |
| Top Flags (data-driven) | HTMX-loaded sidebar widget (`hx-get="/sidebar/flags"`) | Jinja2 macro with template var | `<FlagQueue>` component with `useQuery` |
| Validator-only: hide nav groups | Server-side template conditional | Server-side template conditional | Conditional render based on auth context |

---

## Session State

| Streamlit | FastAPI+Jinja2+HTMX | Flask+Jinja2+HTMX | React+Tailwind |
|-----------|--------------------|--------------------|----------------|
| `st.session_state` (in-memory) | `request.session` (starlette-sessions or cookie) | `flask.session` (cookie-based) | Zustand / Jotai atom store |
| `property_id` in session | `session["property_id"]` | `session["property_id"]` | Context Provider + localStorage |
| `selected_turnover_id` | URL path param `/turnovers/{id}` | URL path param | URL param via React Router |
| `board_filter` passthrough | Query param `?filter=SLA_RISK` | Query param | URL search param |
| `mw_focus_repair_queue` (one-shot) | Session flash: `request.session["flash"]` | `flask.flash()` | Toast state + auto-clear |
| `_admin_app_user_flash` (one-shot) | Session flash | `flask.flash()` | Toast notification |
| `access_mode` | JWT claim or session key | Session key | Auth store atom |
| `board_info_editor` / `board_task_editor` (widget reset) | N/A — use component key in React or page redirect | N/A | Component `key` prop change forces remount |

---

## Layout Primitives

| Streamlit | FastAPI+Jinja2+HTMX | Flask+Jinja2+HTMX | React+Tailwind |
|-----------|--------------------|--------------------|----------------|
| `st.container(border=True)` | `<div class="border rounded p-4">` | `<div class="border rounded p-4">` | `<Card>` component |
| `st.columns([1,2,1])` | CSS Grid or Flexbox | CSS Grid or Flexbox | `<div class="grid grid-cols-4">` |
| `st.tabs(["A","B"])` | `<div class="tabs"> + HTMX` or CSS-only tabs | Tab partial swap with HTMX | `<Tabs>` component (Headless UI / Radix) |
| `st.expander("...")` | `<details><summary>` | `<details><summary>` | `<Accordion>` |
| `st.metric(label, value)` | `<div class="stat">` template partial | `<div class="stat">` | `<MetricCard>` component |
| `st.caption("...")` | `<p class="text-sm text-gray-500">` | `<p class="text-muted">` | `<p className="text-sm text-gray-500">` |
| `st.info/warning/error/success` | Bootstrap/Tailwind alert div | Bootstrap alert div | `<Alert variant="info">` |

---

## Forms & Inputs

| Streamlit | FastAPI+Jinja2+HTMX | Flask+Jinja2+HTMX | React+Tailwind |
|-----------|--------------------|--------------------|----------------|
| `st.form` + `form_submit_button` | `<form method="POST">` | `<form method="POST">` | `<form onSubmit>` |
| `on_change` autosave | `hx-post="..." hx-trigger="change"` | HTMX `hx-post` on blur/change | Controlled input + debounced `useMutation` |
| `st.text_input` | `<input type="text">` | `<input type="text">` | `<Input>` |
| `st.selectbox` | `<select>` | `<select>` | `<Select>` |
| `st.multiselect` | `<select multiple>` or custom | `<select multiple>` | Multi-select component |
| `st.date_input` | `<input type="date">` | `<input type="date">` | DatePicker component |
| `st.checkbox` | `<input type="checkbox">` | `<input type="checkbox">` | `<Checkbox>` |
| `st.file_uploader` | `<input type="file">` + multipart | `<input type="file">` | File input + FormData |
| `st.text_area` | `<textarea>` | `<textarea>` | `<Textarea>` |

---

## Data Tables & Grids

| Streamlit | FastAPI+Jinja2+HTMX | Flask+Jinja2+HTMX | React+Tailwind |
|-----------|--------------------|--------------------|----------------|
| `st.dataframe` (read-only) | HTML `<table>` with sort | HTML `<table>` with sort | TanStack Table (read-only mode) |
| `st.data_editor` (editable grid) | HTMX-patched table rows | HTMX-patched table rows | AG Grid / TanStack Table with editing |
| Diff-and-save pattern | PATCH per changed cell or batch | PATCH per changed cell | Row dirty-state tracking + save handler |
| `SelectboxColumn` | `<select>` in table cell | `<select>` in cell | Custom cell renderer with Select |
| `DateColumn` | `<input type="date">` in cell | `<input type="date">` in cell | DatePicker cell renderer |
| `CheckboxColumn` (▶) | Checkbox + `hx-get="/turnovers/{id}"` | Checkbox + redirect | Checkbox cell + `onRowSelect` callback |
| Row-key stability | Always use `turnover_id` as row key | Always use `turnover_id` | `getRowId` → `row.turnover_id` |
| Dynamic task columns | Server-renders column headers from task types | Same | Dynamic column def generation |

**Critical:** In a migration, replace row-index-based mutation identity with explicit `turnover_id`/`task_id` row keys in all grids.

---

## Mutations & Cache

| Streamlit | FastAPI+Jinja2+HTMX | Flask+Jinja2+HTMX | React+Tailwind |
|-----------|--------------------|--------------------|----------------|
| `st.cache_data.clear()` | Evict cache key or set `Cache-Control: no-store` | `cache.delete(key)` | `queryClient.invalidateQueries(["board"])` |
| `st.rerun()` after mutation | Redirect or HTMX response with updated partial | Redirect + PRG pattern | Optimistic update or refetch |
| `st.cache_data(ttl=30)` | HTTP cache headers + server cache (Redis/memory) | Flask-Caching with TTL | React Query `staleTime: 30_000` |
| `WritesDisabledError` displayed as `st.warning` | HTTP 423 response → toast warning | Flash message | Error boundary / toast system |
| Coarse `cache_data.clear()` | Fine-grained cache key invalidation | Fine-grained | `queryClient.invalidateQueries` by key |

---

## Auth

| Streamlit | FastAPI+Jinja2+HTMX | Flask+Jinja2+HTMX | React+Tailwind |
|-----------|--------------------|--------------------|----------------|
| Inline login form in main area | Dedicated `/login` route + template | Dedicated login Blueprint | `/login` route + auth context |
| `AUTH_DISABLED` | Dev middleware bypass | `LOGIN_DISABLED` config | Dev env auth bypass |
| `LEGACY_AUTH_SOURCE=env` | Config-driven credential check | Config-driven | N/A (server-side only) |
| `LEGACY_AUTH_SOURCE=db` | DB lookup + Argon2 | DB lookup + Argon2 | Server-side (API handles auth) |
| `access_mode` session key | JWT claim `access_mode` | Session key | Auth store + role-based routes |
| `require_auth()` → `st.stop()` | FastAPI dependency `Depends(require_auth)` | `@login_required` decorator | Route guard component |

---

## File Operations

| Streamlit | FastAPI+Jinja2+HTMX | Flask+Jinja2+HTMX | React+Tailwind |
|-----------|--------------------|--------------------|----------------|
| `st.file_uploader` + bytes in session | `<form enctype="multipart/form-data">` POST | `request.files["file"]` | `<input type="file">` + `FormData` fetch |
| `st.download_button(data=bytes)` | `Response(content=bytes, media_type=...)` + `<a download>` | `send_file()` | `URL.createObjectURL(blob)` + `<a download>` |
| Bytes held in session state | **Do not hold in session** — stream from temp file or object storage | `send_file()` streaming | Presigned URL or streaming response |
| "Prepare then download" two-step | Background task (`asyncio` / worker) + polling or SSE | Background thread + polling | `useMutation` → status poll or SSE |

---

## AI Agent Screen

| Streamlit | FastAPI+Jinja2+HTMX | Flask+Jinja2+HTMX | React+Tailwind |
|-----------|--------------------|--------------------|----------------|
| `st.chat_message` | `<div class="message user/assistant">` | Template macro | `<ChatMessage>` component |
| `st.chat_input` | `<form hx-post="/ai/chat" hx-swap="beforeend">` | HTMX form | Controlled `<ChatInput>` |
| Session-held messages | Server-side session or DB | Server-side session | Zustand chat store or React Query |
| Streaming responses | SSE endpoint + HTMX SSE extension | SSE endpoint | `fetch` with `ReadableStream` |
| Property context via `build_context` | Pass `property_id` + `phase_scope` to AI route | Same | API call includes property context |

---

## Admin Control Plane

| Streamlit | FastAPI+Jinja2+HTMX | Flask+Jinja2+HTMX | React+Tailwind |
|-----------|--------------------|--------------------|----------------|
| DB writes toggle (checkbox → DB) | Admin API `PATCH /system/writes-enabled` | Admin route | Toggle component → API call |
| Phase scope (multiselect + apply) | `POST /admin/phase-scope` | Admin route POST | Multi-select + submit |
| Unit master CSV import | `POST /admin/import/unit-master` (multipart) | Upload route | File upload + progress |
| User management (forms in expanders) | Dedicated `/admin/users` CRUD routes | Blueprint routes | Admin users page |
| Flash messages via session pop | `flash()` or response JSON `{message}` | `flash()` | Toast notification system |
| Long-running import (synchronous) | Background task + status endpoint | Worker + polling | Async import with progress bar |

---

## Operations Schedule

| Streamlit | Equivalent | Notes |
|-----------|-----------|-------|
| Manager: `st.data_editor` with save button | Editable table with batch PATCH | `POST /schedule/batch-update` |
| Vendor: `st.dataframe` read-only | HTML `<table>` or read-only grid | CSS only, no JS needed |
| Task type filter (multiselect) | `<select multiple>` + filter client-side or query param | Can be client-side for small lists |

---

## Export Reports

| Streamlit | Equivalent | Notes |
|-----------|-----------|-------|
| Synchronous blob prep on button click | Background job + polling (or streaming) | Move heavy XLSX/ZIP generation off main thread |
| Bytes in session state | Temp file on disk or object storage URL | Session state for binary blobs is a memory hazard at scale |
| `download_button` per format | `<a href="/exports/{run_id}/{format}" download>` | Clean URL-based downloads |
| `export_prepare_error` persistent state | API response `{status, error}` | Standard HTTP error codes |

---

## Risk Radar

| Streamlit | Equivalent | Notes |
|-----------|-----------|-------|
| Sorted `st.dataframe` | HTML table sorted server-side by risk_score DESC | Simple table, no editing needed |
| Emoji risk levels | CSS class-based color + text label | `risk-high`, `risk-medium`, `risk-low` CSS classes |
| Live filters (selectbox + text input) | Client-side filter on pre-loaded table data | Small data set; client filtering fine |

---

## Flag Bridge

| Streamlit | Equivalent | Notes |
|-----------|-----------|-------|
| `st.data_editor` with ▶ checkbox nav | `<table>` with row-click or explicit "Open" button | ▶ checkbox is confusing UX; replace with explicit "View" link/button |
| Breach filter categories | Query param + server filter | `?breach=SLA_RISK` |
| Complex breach detection (`_filter_by_bridge`) | Same server-side logic, moved to service layer | Already in service, just expose via API |

---

## Summary: Recommended Approach

For **FastAPI+Jinja2+HTMX** (server-rendered, progressive enhancement):
- Navigation: URL paths + HTMX partial swaps
- Data grids: HTMX-enhanced HTML tables; editable cells as inline `hx-post` inputs
- Session: `starlette-sessions` with cookie backend
- Auth: FastAPI `Depends()`-based guards + JWT or session

For **React+Tailwind** (SPA):
- Navigation: React Router with URL params (`/turnovers/{id}`)
- Data grids: TanStack Table or AG Grid
- Session: Zustand + React Query
- Auth: JWT claims in memory + refresh token in HTTP-only cookie

For **hybrid** (FastAPI API + React frontend — recommended):
- FastAPI serves a REST API (`/api/...`)
- React handles all UI rendering
- React Query for caching/invalidation
- Real URLs for all entities

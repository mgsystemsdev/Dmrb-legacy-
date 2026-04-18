# DMRB Legacy — UI Migration Blueprint

> High-level execution plan for migrating from Streamlit to FastAPI REST API + React + Tailwind.
> Based on full codebase analysis and UX audit. Analysis date: 2026-04-17

---

## Migration Philosophy

1. **Keep the service layer.** `services/`, `db/`, `domain/` are clean. Do not rewrite them. The migration adds a REST API surface on top of existing services.
2. **Real URLs first.** The single biggest UX improvement. Introduce proper routing in Phase 2 before anything else.
3. **Screen parity before improvement.** Replicate each screen to functional parity first. Layer in improvements (real URLs, concurrent edit, streaming) as a second pass.
4. **Run both apps in parallel.** Streamlit stays live. React app deploys incrementally. Cut over screen by screen.
5. **Centralize duplicated logic on the way out.** Status mappings, QC logic, breach detection — consolidate into services as you build the API layer.

---

## Architecture Target

```
PostgreSQL (unchanged)
    ↑
Services layer (unchanged: services/, db/, domain/)
    ↑
FastAPI REST API — new surface layer
  /api/properties/
  /api/board/{property_id}
  /api/turnovers/{id}
  /api/turnovers/{id}/tasks
  /api/turnovers/{id}/notes
  /api/turnovers/{id}/audit
  /api/schedule/{property_id}
  /api/admin/...
  /api/ai/chat
  /api/exports/...
  /api/imports/...
    ↑ JSON
React Frontend (new)
  /board
  /turnovers/:id
  /schedule
  /morning
  /flags
  /risk
  /import
  /export
  /admin
  /ai
```

---

## Phase 1: FastAPI REST API Layer

**Goal:** Expose all existing services as JSON endpoints. No UI work yet.

### 1.1 Project Setup

```
backend/
  api/
    routes/
      board.py
      turnovers.py
      admin.py
      schedule.py
      imports.py
      exports.py
      ai.py
      auth.py
    deps.py          # FastAPI Depends() for auth, property_id
    models.py        # Pydantic response models
  main.py            # FastAPI app + router registration
```

### 1.2 Auth Endpoint

- `POST /api/auth/login` → validates credentials (env or DB mode), returns session or JWT
- `POST /api/auth/logout` → clears session
- `GET /api/auth/me` → returns `{user_id, username, access_mode}`

### 1.3 Board Endpoints

- `GET /api/board/{property_id}` → calls `board_service.get_board()`, returns board rows as JSON
- `GET /api/board/{property_id}/flags` → calls `board_service.get_flag_units()`, returns flag categories
- `PATCH /api/turnovers/{id}/fields` → body: `{field, value, actor, source}`; calls appropriate service

### 1.4 Turnover Endpoints

- `GET /api/turnovers/{id}` → calls `unit_service.get_unit_detail()`, returns full detail dict
- `PATCH /api/turnovers/{id}` → field updates (status, dates, legal)
- `GET /api/turnovers/{id}/tasks` → returns task list
- `PATCH /api/turnovers/{id}/tasks/{task_id}` → execution status, assignee, due date, required, blocking
- `GET /api/turnovers/{id}/notes` → returns notes
- `POST /api/turnovers/{id}/notes` → add note
- `PATCH /api/turnovers/{id}/notes/{note_id}/resolve` → resolve note
- `GET /api/turnovers/{id}/audit` → audit history
- `POST /api/turnovers` → create turnover (admin)
- `DELETE /api/turnovers/{id}` → cancel turnover (soft delete)

### 1.5 Schedule Endpoints

- `GET /api/schedule/{property_id}` → returns task schedule rows
- `PATCH /api/schedule/batch` → body: `[{task_id, vendor_due_date?, assignee?, execution_status?}]`

### 1.6 Admin Endpoints

- `GET /api/system/writes-enabled` → returns `{enabled: bool}`
- `PATCH /api/system/writes-enabled` → body: `{enabled: bool}`
- `GET /api/properties` → all properties
- `POST /api/properties` → create property
- `GET /api/admin/phase-scope/{property_id}` → current phase scope
- `PATCH /api/admin/phase-scope/{property_id}` → body: `{phase_ids: [...]}`
- `GET /api/admin/users` → app user list
- `POST /api/admin/users` → create user
- `PATCH /api/admin/users/{uid}/password` → update password
- `PATCH /api/admin/users/{uid}/role` → update role

### 1.7 Import / Export Endpoints

- `POST /api/imports/unit-master` → multipart CSV upload; returns `{created, skipped, errors}`
- `POST /api/imports/reports/{report_type}` → CSV upload for move-outs, pending-move-ins, etc.
- `POST /api/exports/prepare` → triggers background export generation; returns `{job_id}`
- `GET /api/exports/{job_id}/status` → `{status, ready_formats: [...]}`
- `GET /api/exports/{job_id}/{format}` → streams file (XLSX, TXT, PNG, ZIP)

### 1.8 AI Chat Endpoint

- `POST /api/ai/sessions` → create session with `property_id`
- `POST /api/ai/sessions/{session_id}/messages` → SSE streaming response

### 1.9 Consolidation During Phase 1

When building API routes, centralize these duplications:
- **Status mapping** (`_board_status_to_db` / `_unit_detail_status_to_fields`): extract to `services/status_mapping.py`
- **QC label mapping**: extract to same module
- **Breach detection** (`_filter_by_bridge` / `board_breach_row_display`): move to `services/breach_service.py`

**Deliverable:** Full REST API documented with OpenAPI (auto-generated by FastAPI). Streamlit app continues serving. Both can share the same DB.

---

## Phase 2: React Shell, Auth, Routing, Sidebar

**Goal:** React app bootstraps, authenticates, renders sidebar and property selector. Navigation works.

### 2.1 Project Setup

```
frontend/
  src/
    api/          # API client (React Query wrappers)
    components/   # Shared UI components
      Sidebar.tsx
      NavGroup.tsx
      PropertySelector.tsx
      FlagQueue.tsx
    pages/        # Screen-level components
    stores/       # Zustand stores (auth, property)
    router.tsx    # React Router setup
    App.tsx
  vite.config.ts
  tailwind.config.ts
```

### 2.2 Auth Store

```typescript
// stores/auth.ts
interface AuthState {
  user: { userId, username, accessMode } | null;
  login: (credentials) => Promise<void>;
  logout: () => void;
}
```

### 2.3 Sidebar Component

Replicates `_NAV_GROUPS` structure as static config. Highlights active route. Validator-only mode hides all groups except W/O Validator.

### 2.4 Property Context

`PropertyContext` provider wraps app. `useProperty()` hook returns `{ propertyId, setPropertyId }`. All API calls use `propertyId` from context.

### 2.5 Route Guard

```typescript
// Equivalent to require_auth() + validator_only enforcement
<Route path="/board" element={<RequireAuth accessMode="full"><Board /></RequireAuth>} />
<Route path="/work-order-validator" element={<RequireAuth><WorkOrderValidator /></RequireAuth>} />
```

**Deliverable:** React app deploys alongside Streamlit. Auth and navigation work. All 15 routes defined (even if pages show placeholder).

---

## Phase 3: Board Screen

**Goal:** Replicate board with AG Grid. Full parity with board + unit tasks tabs.

### 3.1 AG Grid Setup

```typescript
// Board grid with stable row keys
const colDefs: ColDef[] = [
  { field: "navigate", headerName: "▶", cellRenderer: "navigateCell", width: 40 },
  { field: "unit_code", headerName: "Unit", editable: false },
  // ... status, dates, QC
  // Dynamic task columns built from API response
];

const gridOptions = {
  getRowId: (row) => row.data.turnover_id.toString(),
  onCellValueChanged: (event) => handleMutation(event),
};
```

### 3.2 Dynamic Task Columns

API returns `task_types_present` alongside board rows. Frontend builds AG Grid `ColDef[]` dynamically from this list, ordered by `TASK_COLS`.

### 3.3 Filters

Controlled inputs above grid. React Query `queryKey` includes filter state — changing filters refetches board from API.

### 3.4 `board_filter` Passthrough

React Router `useSearchParams()` reads `?filter=SLA_RISK`. Board reads search param on mount and pre-filters. "Clear Filter" removes param.

### 3.5 Mutations

```typescript
const { mutate: updateField } = useMutation({
  mutationFn: (data: { field, value }) =>
    api.patch(`/turnovers/${turnoverData.id}/fields`, data),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["board", propertyId] }),
});
```

**Deliverable:** Board screen at `/board` with full parity: live filters, two tabs, inline editing, row-select navigation.

---

## Phase 4: Unit Detail Screen

**Goal:** Full unit detail with autosave, task grid, notes, audit.

### 4.1 URL

`/turnovers/:id` — replaces `selected_turnover_id` session state. Bookmark/share-friendly.

### 4.2 Autosave Pattern

```typescript
// Controlled input with debounced mutation
const { mutate } = useMutation({ mutationFn: updateTurnoverField });
const handleChange = useMemo(
  () => debounce((field, value) => mutate({ field, value }), 400),
  [mutate]
);
```

Show brief "Saved ✓" badge after mutation resolves.

### 4.3 Task Grid

Simple vertical list (not a data grid). Each task renders as a row with its own controlled inputs. Per-task `useMutation` calls.

### 4.4 Notes & Audit

Loaded lazily when expanders open (separate API queries, not on initial page load).

**Deliverable:** Unit detail at `/turnovers/:id`. Shareable URL. Autosave with visual feedback.

---

## Phase 5: Operational Screens

**Goal:** Morning Workflow, Operations Schedule, Flag Bridge, Risk Radar.

Each screen maps its filter state to URL query params. Mutations follow Phase 3/4 patterns.

| Screen | Key behavior to replicate |
|--------|--------------------------|
| Morning Workflow | Top action buttons set `?filter=` and navigate to `/board`. Repair queue one-shot flag via React state (not URL). Missing move-out editor with date column. |
| Operations Schedule | Manager: AG Grid editable (Date, Assignee, Status) with batch save. Vendor: read-only HTML table. Task type filter multiselect. |
| Flag Bridge | Read-only AG Grid. Row "View" button (replace ▶ checkbox) navigates to `/turnovers/:id`. Breach filter categories as tabs or selectbox. |
| Risk Radar | Read-only HTML table sorted by risk_score DESC. Client-side filter (small dataset). CSS color classes replace emoji. |

---

## Phase 6: Admin, Import, Export Screens

**Goal:** Admin control plane, file import flows, export downloads.

| Screen | Notes |
|--------|-------|
| Admin | DB writes toggle via `PATCH /system/writes-enabled`. Confirmation modal for phase scope. Flash messages via Sonner toast. |
| Unit Master Import | `<input type="file">` + FormData POST. Show result summary (created/skipped/errors). |
| Import Console | CSV upload per report type. Ordered import flow per `docs/IMPORT_REBUILD_ORDER.md`. |
| Export Reports | `POST /exports/prepare` → background job. Poll `GET /exports/{job_id}/status`. Render download links when ready. No bytes in session state. |
| Work Order Validator | File upload + server-side validation + download link. |

---

## Phase 7: AI Agent

**Goal:** Chat UI with server-side session persistence and streaming responses.

- `POST /ai/sessions` creates a DB-backed session with `property_id`
- `POST /ai/sessions/{id}/messages` → SSE stream
- React `useRef(eventSource)` + append chunks to message state
- Load existing sessions on mount

---

## Improvements to Implement During Migration

| Improvement | When |
|-------------|------|
| Centralize status/QC mapping | Phase 1 (API layer) |
| Real URLs for all entities | Phase 2 (routing) |
| Stable row keys in grids | Phase 3 (board) |
| Pop `board_task_editor` in Streamlit | Fix now (one-line change) |
| Fine-grained cache invalidation | Phase 3+ |
| Autosave visual feedback | Phase 4 |
| Concurrent edit protection (ETags) | Phase 4 |
| Async export generation | Phase 6 |
| AI session persistence | Phase 7 |
| Replace emoji-only status with CSS classes | Phase 3+ |
| Confirmation modal for phase scope | Phase 6 |

---

## What to Replicate Exactly

- All 10 critical behaviors from `04-preservation-checklist.md`
- `TASK_COLS` canonical column order (copy to frontend constants)
- `EXEC_MAP`, `EXEC_REV`, `EXEC_LABELS`, `EXEC_LABELS_EXTENDED` (copy to frontend constants)
- `BLOCK_OPTIONS`, `STATUS_OPTIONS`, `WD_OPTS` (copy to frontend constants)
- Breach detection logic (server-side; expose via API)
- Auth modes (env, DB, disabled) — all three must work

## What to Improve, Not Replicate

- ▶ checkbox navigation → explicit "View" button
- Flat session state → URL params + typed store
- Coarse cache clear → fine-grained query invalidation
- Sync export blobs in session → async job + download URL
- Emoji-only status encoding → CSS classes + text labels
- Silent autosave → visual feedback ("Saved ✓")
- No concurrent edit protection → ETag/version-based conflict detection
- AI session in memory → DB-persisted sessions

---

## Testing Strategy for Migration

- [ ] Board loads with correct property + phase scope for all test properties
- [ ] Inline status edit persists to DB and reloads with updated value
- [ ] ▶ row-select navigates to `/turnovers/{id}` with correct data
- [ ] `board_filter=SLA_RISK` passed from Morning Workflow shows filtered board
- [ ] Unit detail autosave: change date → verify in DB without page reload
- [ ] Unit detail back → returns to board at correct scroll position
- [ ] Validator-only login → only Work Order Validator accessible
- [ ] DB writes OFF → all edits show warning, no DB change
- [ ] Export: prepare → download ZIP → verify file contents
- [ ] Import: upload Units.csv → verify unit_master updated
- [ ] Phase scope change → board reloads with new scope
- [ ] Concurrent edit: two users edit same turnover → second save rejected with conflict message
- [ ] AI chat: send message → streaming response renders incrementally
- [ ] Refresh `/turnovers/1234` → detail page loads directly (not board)

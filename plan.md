Context

     Complete replacement of the Streamlit app (15 screens) with FastAPI (REST API) + React (UI).
     The existing HTMX work (templates, pages.py) will be removed — React takes over all rendering.
     The service layer stays completely unchanged. The FastAPI app stays as the backend.

     ---
     Architecture

     PostgreSQL (unchanged)
         ↑
     services/ + db/ + domain/ (unchanged)
         ↑
     FastAPI — /api/... (JSON only, no HTML)
         ↑ fetch / React Query
     React (frontend/) — Vite + React + TypeScript
       AG Grid        — board, schedule, flag bridge
       React Query    — server state + cache invalidation
       React Router   — real URLs for all screens
       Tailwind CSS   — styling (via npm, no standalone CLI needed)
       Zustand        — auth + property context

     FastAPI serves the React build from / so it's one deployment unit.

     ---
     What to Remove (HTMX work no longer needed)

     - api/routers/pages.py — delete (React replaces all HTML pages)
     - api/templates/ — delete entire directory
     - tailwind.config.js (root level) — delete (Tailwind moves inside frontend/)
     - static/input.css — delete
     - nginx.conf — simplify (no Streamlit proxy needed at the end)

     Keep:
     - api/main.py — update to serve React build + JSON API
     - api/middleware/ — keep auth (update to return JSON 401 always, no HTML redirect)
     - api/routers/board.py — keep JSON endpoint, remove HTMX rows endpoint
     - api/routers/imports.py — keep

     ---
     Phase 1: FastAPI API Layer (complete before any React work)

     Build all JSON endpoints the React app will need.

     Auth (already mostly done)

     - POST /api/login — already exists
     - POST /api/logout — already exists
     - GET /api/auth/me → returns {user_id, username, role, access_mode}

     Properties

     - GET /api/properties → list all properties
     - GET /api/properties/{pid}/phases → phases for cascading form
     - GET /api/phases/{id}/buildings → buildings for cascading form
     - GET /api/buildings/{id}/units → units for cascading form

     Board

     - GET /api/board/{property_id} → already exists (extend with more fields)
     - GET /api/board/{property_id}/flags → sidebar flag queue

     Turnovers

     - GET /api/turnovers/{id} → full unit detail dict
     - POST /api/turnovers → create turnover
     - PATCH /api/turnovers/{id} → update fields (status, dates, legal, W/D)
     - DELETE /api/turnovers/{id} → cancel turnover
     - GET /api/turnovers/{id}/audit → audit history

     Tasks

     - GET /api/turnovers/{id}/tasks → task list for unit detail
     - PATCH /api/turnovers/{id}/tasks/{task_id} → update execution_status, due_date, assignee, required,
     blocking

     Notes

     - GET /api/turnovers/{id}/notes → note list
     - POST /api/turnovers/{id}/notes → add note
     - PATCH /api/notes/{note_id}/resolve → resolve note

     Schedule

     - GET /api/schedule/{property_id} → task schedule rows
     - POST /api/schedule/{property_id}/batch → batch update (date, assignee, status)

     Morning Workflow

     - GET /api/morning/{property_id} → metrics, critical units, missing move-outs

     Risk

     - GET /api/risk/{property_id} → risk dashboard rows

     Exports

     - POST /api/exports/{property_id}/prepare → triggers generation, returns {job_id}
     - GET /api/exports/{job_id}/status → {status, formats_ready}
     - GET /api/exports/{job_id}/{format} → stream file (xlsx, txt, png, zip)

     Imports

     - POST /api/imports/{property_id}/{report_type} → CSV upload, returns {batch_id}
     - GET /api/imports/{batch_id}/status → already exists
     - GET /api/imports/{property_id}/history → import history
     - GET /api/imports/{property_id}/missing-moveouts → missing move-out list
     - GET /api/imports/{property_id}/overrides → override conflicts
     - POST /api/imports/overrides/{id}/accept or /keep
     - GET /api/imports/{property_id}/invalid → invalid data rows
     - POST /api/imports/invalid/{id}/correct → apply correction

     Admin

     - GET /api/admin/writes-enabled → {enabled: bool}
     - PATCH /api/admin/writes-enabled → toggle
     - PATCH /api/admin/{property_id}/phase-scope → update active phases
     - POST /api/admin/import/unit-master → CSV upload
     - GET /api/admin/users → user list
     - POST /api/admin/users → create user
     - PATCH /api/admin/users/{id}/password → update password
     - PATCH /api/admin/users/{id}/role → change role
     - PATCH /api/admin/users/{id}/active → enable/disable

     Work Order Validator

     - POST /api/validator/upload → upload + classify, returns {job_id}
     - GET /api/validator/{job_id}/status
     - GET /api/validator/{job_id}/download/{format} → stream file

     AI Agent

     - GET /api/ai/sessions → session list
     - POST /api/ai/sessions → create session (body: {property_id})
     - DELETE /api/ai/sessions/{id}
     - POST /api/ai/sessions/{id}/messages → SSE streaming response

     ---
     Phase 2: React Project Setup

     frontend/
       src/
         api/           # React Query hooks (useBoard, useTurnover, etc.)
         components/    # Shared UI (Sidebar, PropertySelector, StatusBadge, etc.)
         pages/         # One file per screen
         stores/        # Zustand (useAuth, useProperty)
         lib/           # utils, constants (TASK_COLS, STATUS_OPTIONS, EXEC_MAP etc.)
         router.tsx     # React Router setup
         App.tsx
       index.html
       vite.config.ts
       tailwind.config.ts
       tsconfig.json
       package.json

     Key dependencies:
     {
       "react": "^18",
       "react-router-dom": "^7",
       "@tanstack/react-query": "^5",
       "ag-grid-react": "^32",
       "ag-grid-community": "^32",
       "zustand": "^5",
       "tailwindcss": "^3",
       "sonner": "^1",
       "axios": "^1"
     }

     FastAPI serves React build:
     # api/main.py — add at end, after all /api routes
     app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="spa")

     Auth flow: JWT/cookie from FastAPI → stored in Zustand → sent with every request via axios interceptor.
     On 401 → redirect to /login.

     Constants to copy from Streamlit into frontend/src/lib/constants.ts:
     - TASK_COLS, TASK_DISPLAY, STATUS_OPTIONS, EXEC_MAP, EXEC_REV, EXEC_LABELS, BLOCK_OPTIONS,
     READINESS_LABELS

     ---
     Phase 3: Core Shell (Auth + Sidebar + Routing)

     Routes:
     /login               → LoginPage
     /board/:propertyId   → BoardPage
     /unit/:turnoverId    → UnitDetailPage
     /schedule/:propertyId → SchedulePage
     /morning/:propertyId → MorningWorkflowPage
     /flags/:propertyId   → FlagBridgePage
     /risk/:propertyId    → RiskRadarPage
     /import/:propertyId  → ImportConsolePage
     /import-reports/:propertyId → ImportReportsPage
     /exports/:propertyId → ExportReportsPage
     /validator           → WorkOrderValidatorPage
     /admin               → AdminPage
     /add-turnover/:propertyId → AddTurnoverPage
     /structure/:propertyId → PropertyStructurePage
     /ai                  → AIAgentPage

     Sidebar component:
     - Logo + property selector (onChange → navigate to same page with new propertyId)
     - 4 nav groups (Quick Tools, Daily Ops, Import & Reports, Administration)
     - Top Flags section — React Query polling GET /api/board/{pid}/flags
     - Validator-only mode: show only W/O Validator link
     - Active route highlighted

     Property context (Zustand):
     // stores/useProperty.ts
     { propertyId, setPropertyId }
     // All pages read propertyId from here, not URL (except for deep links)

     ---
     Phase 4: Board Screen (AG Grid)

     AG Grid setup:
     const colDefs: ColDef[] = [
       { field: "unit_code", headerName: "Unit", width: 90 },
       { field: "status", headerName: "Status", editable: true,
         cellEditor: "agSelectCellEditor",
         cellEditorParams: { values: STATUS_OPTIONS } },
       { field: "move_out_date", headerName: "Move-Out", editable: true,
         cellEditor: "agDateCellEditor" },
       // ... ready_date, move_in_date, QC
       // Dynamic task columns generated from taskTypes array
     ]

     const gridOptions = {
       getRowId: (p) => p.data.turnover_id.toString(),
       onCellValueChanged: (e) => mutateTurnoverField(e),
     }

     Two tabs: Unit Info tab + Unit Tasks tab (separate AG Grid instances, same data).

     Filters: Controlled inputs above grid. Filter state in URL search params (?search=&phase=&nvm=). React
     Query key includes filter state.

     Row click → unit detail: onRowClicked → navigate('/unit/' + row.turnover_id).

     Mutations:
     const { mutate } = useMutation({
       mutationFn: ({ id, field, value }) =>
         api.patch(`/api/turnovers/${id}`, { field, value }),
       onSuccess: () => queryClient.invalidateQueries({ queryKey: ['board', propertyId] }),
     })

     ---
     Phase 5: Unit Detail Screen

     URL: /unit/:turnoverId

     7 panels (accordion or sections):
     1. Unit header — unit code, legal toggle, back button
     2. Status & QC — status select, QC label, SLA indicator
     3. Dates — move-out, ready date, move-in date inputs
     4. W/D — present select, notify/install buttons
     5. Risks — open risk list
     6. Tasks — per-task rows with execution select, assignee, date, required, blocking
     7. Notes — note list + add note form

     Autosave pattern:
     const { mutate } = useMutation({ mutationFn: updateTurnoverField })
     const handleChange = useDebouncedCallback(
       (field, value) => mutate({ id: turnoverData.id, field, value }), 400
     )
     // Show "Saved ✓" toast via Sonner after mutation resolves

     Lazy-loaded panels: Audit history and Authority panels fetch on expand, not on page load.

     ---
     Phase 6: Remaining Screens

     Order by complexity (easiest first):

     ┌───────────────────┬──────────────────────────────────────┬──────────────────────────────────────────┐
     │      Screen       │            Key component             │                  Notes                   │
     ├───────────────────┼──────────────────────────────────────┼──────────────────────────────────────────┤
     │ Risk Radar        │ HTML table (read-only)               │ Client-side filter, sort by risk_score   │
     ├───────────────────┼──────────────────────────────────────┼──────────────────────────────────────────┤
     │ Property          │ Nested accordion                     │ Read-only hierarchy                      │
     │ Structure         │                                      │                                          │
     ├───────────────────┼──────────────────────────────────────┼──────────────────────────────────────────┤
     │ Flag Bridge       │ AG Grid read-only                    │ Row click → unit detail                  │
     ├───────────────────┼──────────────────────────────────────┼──────────────────────────────────────────┤
     │ Morning Workflow  │ Dashboard cards + inline date edit   │ Top action buttons set filter + navigate │
     │                   │                                      │  to board                                │
     ├───────────────────┼──────────────────────────────────────┼──────────────────────────────────────────┤
     │ Operations        │ AG Grid editable (manager) / table   │ Batch save button                        │
     │ Schedule          │ (vendor)                             │                                          │
     ├───────────────────┼──────────────────────────────────────┼──────────────────────────────────────────┤
     │ Add Turnover      │ Cascading select form                │ Phase → Building → Unit                  │
     ├───────────────────┼──────────────────────────────────────┼──────────────────────────────────────────┤
     │ Export Reports    │ Prepare button + download links      │ Poll job status with React Query refetch │
     │                   │                                      │  interval                                │
     ├───────────────────┼──────────────────────────────────────┼──────────────────────────────────────────┤
     │ Import Console    │ 4-tab file upload                    │ Poll batch status                        │
     ├───────────────────┼──────────────────────────────────────┼──────────────────────────────────────────┤
     │ Import Reports    │ 3-tab correction workflow            │ Override + invalid data forms            │
     ├───────────────────┼──────────────────────────────────────┼──────────────────────────────────────────┤
     │ Work Order        │ File upload + classified download    │                                          │
     │ Validator         │                                      │                                          │
     ├───────────────────┼──────────────────────────────────────┼──────────────────────────────────────────┤
     │ Admin             │ 4-tab control plane                  │ User CRUD, phase scope, unit master      │
     │                   │                                      │ import                                   │
     ├───────────────────┼──────────────────────────────────────┼──────────────────────────────────────────┤
     │ AI Agent          │ Chat UI                              │ SSE streaming via EventSource            │
     └───────────────────┴──────────────────────────────────────┴──────────────────────────────────────────┘

     ---
     Phase 7: Remove Streamlit

     1. pip uninstall streamlit + remove from requirements.txt
     2. Delete app.py
     3. Archive ui/ → ui_archive/ (keep for reference, don't delete yet)
     4. Remove HTMX templates: delete api/templates/, api/routers/pages.py
     5. Update api/main.py: remove static CSS mount, ensure React build is served
     6. Update nginx.conf: single upstream to FastAPI on port 8000
     7. pytest tests/ — confirm same pre-existing 6 failures, no regressions

     ---
     Critical Files Modified

     ┌───────────────────────────┬────────────────────────────────────────────────────────┐
     │           File            │                         Change                         │
     ├───────────────────────────┼────────────────────────────────────────────────────────┤
     │ api/main.py               │ Add React build mount, clean up HTMX routes            │
     ├───────────────────────────┼────────────────────────────────────────────────────────┤
     │ api/middleware/auth.py    │ Return JSON 401 always (no HTML redirect needed)       │
     ├───────────────────────────┼────────────────────────────────────────────────────────┤
     │ api/routers/board.py      │ Extend with more fields, remove HTMX fragment endpoint │
     ├───────────────────────────┼────────────────────────────────────────────────────────┤
     │ api/routers/turnovers.py  │ NEW — full turnover CRUD                               │
     ├───────────────────────────┼────────────────────────────────────────────────────────┤
     │ api/routers/properties.py │ NEW — properties + cascading selects                   │
     ├───────────────────────────┼────────────────────────────────────────────────────────┤
     │ api/routers/schedule.py   │ NEW — schedule read + batch update                     │
     ├───────────────────────────┼────────────────────────────────────────────────────────┤
     │ api/routers/admin.py      │ NEW — admin control plane                              │
     ├───────────────────────────┼────────────────────────────────────────────────────────┤
     │ api/routers/ai.py         │ NEW — AI sessions + SSE                                │
     ├───────────────────────────┼────────────────────────────────────────────────────────┤
     │ api/routers/exports.py    │ NEW — prepare + stream downloads                       │
     ├───────────────────────────┼────────────────────────────────────────────────────────┤
     │ api/routers/validator.py  │ NEW — W/O validator                                    │
     ├───────────────────────────┼────────────────────────────────────────────────────────┤
     │ frontend/                 │ NEW — entire React app                                 │
     └───────────────────────────┴────────────────────────────────────────────────────────┘

     ---
     Verification

     - pytest tests/ after Phase 1 — no new failures
     - npm run build in frontend/ — clean build
     - Open http://localhost:8000 → React app loads, login works
     - Board: load, filter, inline status edit → check DB updated
     - Unit detail: change move-out date → persists, "Saved ✓" appears
     - All 15 routes reachable via sidebar nav
     - Streamlit not running, not in requirements.txt
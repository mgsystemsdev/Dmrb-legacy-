# DMRB Legacy — Frontend Approach Recommendation

> Analysis date: 2026-04-17
> Decision: Which frontend framework best serves DMRB's migration from Streamlit?

---

## Options Evaluated

| # | Approach | Stack |
|---|----------|-------|
| A | Server-Rendered | FastAPI + Jinja2 + HTMX |
| B | SPA | React + Tailwind + Vite |
| C | Hybrid (Recommended) | FastAPI REST API + React frontend |
| D | Flask equivalent | Flask + Jinja2 + HTMX |

---

## Option A: FastAPI + Jinja2 + HTMX

### Description
Python-native server-rendered HTML with HTMX for partial page updates. The same team that writes the service layer can write templates. Minimal JavaScript.

### Strengths
- Minimal context switch — Python all the way down
- HTMX handles inline editing (data grids, autosave) well via `hx-post` + `hx-swap`
- No build pipeline; no npm; no bundler
- Server-side auth, sessions, and rendering — no client-side token management
- Easy to add real URLs (FastAPI routes map to Jinja2 templates)

### Weaknesses
- **Data editor grids** — HTMX inline-edit tables work for simple cases but become painful for the DMRB board (dynamic columns, multi-row mutations, CheckboxColumn row-select). Each cell edit becomes an HTTP round-trip.
- **Dynamic task columns** — generating editable columns per task type is complex in Jinja2 templates vs React component generation
- **AI agent streaming** — requires SSE + HTMX SSE extension; more complex than React's native `ReadableStream` support
- **State management** — HTMX partial swaps require careful `hx-target` discipline; complex page state is hard to reason about
- **Onboarding** — HTMX idioms are non-obvious to frontend developers

### Complexity: Low
### Deployment: Simple (single FastAPI process)
### UX Quality: Moderate (server-round-trips on every cell edit feel slow)

---

## Option B: React + Tailwind + Vite (SPA)

### Description
Full SPA: React handles all rendering client-side, communicates with a FastAPI (or Django) REST API. Tailwind for styling. Vite for fast dev build.

### Strengths
- **Data grids** — AG Grid or TanStack Table with React handle DMRB's board perfectly: dynamic columns, cell editing, row-key stability, keyboard navigation
- **Real-time UX** — optimistic updates, React Query for cache invalidation, no full-page reloads
- **AI agent** — native `ReadableStream` for SSE streaming; `<ChatInput>/<ChatMessage>` trivial in React
- **Component reuse** — shared components across board, unit detail, schedule
- **URL routing** — React Router gives free deep links

### Weaknesses
- **Build pipeline** — npm, bundler, TypeScript toolchain (moderate ops overhead)
- **Two codebases** — FastAPI backend + React frontend; two deployment units
- **Auth complexity** — must handle token refresh, CSRF protection on client side
- **More frontend expertise needed** — React, TypeScript, React Query, Tailwind

### Complexity: High (vs. Option A)
### Deployment: Two units (API + static frontend, or containerized)
### UX Quality: High — this is the professional standard for dense operational tools

---

## Option C (Recommended): FastAPI REST API + React Frontend

### Description
FastAPI serves a clean REST API (`/api/...`). React handles all rendering. Deployed together (FastAPI serves built React static files) or separately (Vercel/CDN for React + Railway/Render for API).

### Why This Wins

1. **The board is a data grid product.** The core interaction model (multi-column editable grid, dynamic task columns, row-select navigation, batch mutations) maps cleanly to AG Grid or TanStack Table. Server-rendered HTMX grids are workable but fight the problem shape.

2. **Real URLs are free.** React Router gives `/board`, `/turnovers/1234`, `/admin/users` at zero extra cost. This is the single biggest UX improvement available and it's free in React.

3. **Service layer doesn't change.** DMRB's `services/` layer is already clean (no Streamlit imports). FastAPI controllers are thin wrappers: read from service, return JSON. Migration is surgical.

4. **Same Python team owns the API.** FastAPI feels like Streamlit-without-the-UI — same `services/` calls, same `db/` layer, just a different surface layer. No need to rewrite business logic.

5. **Tailwind tokens replace emoji.** Color system (`text-red-600`, `bg-yellow-100`) replaces emoji-encoded statuses. Accessible, printable, theming-friendly.

6. **React Query replaces `cache_data`.** `staleTime: 30_000` + `queryClient.invalidateQueries(["board", propertyId])` replaces the blunt `st.cache_data.clear()`. Fine-grained invalidation per mutation.

### Tradeoffs vs. HTMX

| Dimension | FastAPI+HTMX | FastAPI+React |
|-----------|-------------|---------------|
| Setup time | 1 day | 3 days |
| Board grid quality | Moderate | High |
| Concurrent edit UX | Hard | Straightforward |
| AI agent streaming | Workable | Native |
| Long-term maintainability | Lower (HTMX at scale) | Higher |
| Ops overhead | Low | Medium |
| Onboarding new devs | HTMX-specific learning | Standard React ecosystem |

### Architecture

```
FastAPI (backend)
  /api/properties/
  /api/board/{property_id}
  /api/turnovers/{id}
  /api/admin/...
  /api/ai/chat
  ↕ (served from same origin or CORS)
React (frontend)
  /board
  /turnovers/:id
  /schedule
  /admin
  /ai
  ...
```

FastAPI serves React's built static files from `/static/` (or separate CDN). Single deployment unit possible.

---

## Option D: Flask + Jinja2 + HTMX

Same analysis as Option A but:
- Flask has no native async — HTMX partial updates are synchronous (worse for AI streaming)
- FastAPI's type hints and `Depends()` dependency injection are significantly better for a codebase of DMRB's complexity
- Flask is not recommended over FastAPI for a new migration

---

## Recommendation: Option C

**FastAPI REST API + React + Tailwind + React Query + TanStack Table or AG Grid**

### Specific Library Recommendations

| Need | Library | Why |
|------|---------|-----|
| Data grid (board) | AG Grid Community | Free, handles dynamic columns, row keys, editable cells natively |
| Data table (read-only) | TanStack Table | Lightweight, headless, perfect for flag bridge / risk radar |
| State management | Zustand | Minimal, no boilerplate, works well with React Query |
| Server state / cache | React Query (TanStack Query) | Stale-while-revalidate, `invalidateQueries` for precise invalidation |
| Routing | React Router v7 | Real URLs, nested routes, `useParams` for `turnover_id` |
| Styling | Tailwind CSS | Utility-first, no CSS conflicts, tokens map to design system |
| Date inputs | react-day-picker | Accessible, headless, matches date patterns in DMRB |
| Multi-select | Headless UI Combobox | Accessible, works with Tailwind |
| Toast notifications | Sonner | Minimal, no setup, replaces all flash/warning patterns |
| AI streaming | Native `fetch` + `ReadableStream` | Built-in, no library needed |
| File download | `URL.createObjectURL` | Works for all export formats |

### Migration Path

1. **Phase 1:** FastAPI REST API (expose existing services as JSON endpoints)
2. **Phase 2:** React shell — sidebar, routing, property context
3. **Phase 3:** Board screen (AG Grid, filters, row-select)
4. **Phase 4:** Unit detail (autosave form, task grid)
5. **Phase 5:** Remaining screens (schedule, morning workflow, flag bridge, risk radar)
6. **Phase 6:** Admin + export + import screens
7. **Phase 7:** AI agent (streaming chat)

---

## Deployment

### Simple (single process)
```
FastAPI builds + serves React static output
uvicorn app:app --port 8000
```

### Scalable (two services)
```
API:      Railway / Render / Fly.io (FastAPI)
Frontend: Vercel / Netlify (React static)
DB:       Existing PostgreSQL (unchanged)
```

The existing `DATABASE_URL` and PostgreSQL schema are unchanged in either deployment model.

---

## Estimated Effort

| Phase | Screens/Work | Effort |
|-------|-------------|--------|
| FastAPI API layer | 15 screens × avg 3 endpoints | 1–2 weeks |
| React shell + routing | Shell, sidebar, auth | 3 days |
| Board screen | Grid, filters, mutations | 1 week |
| Unit detail | Form, task grid, autosave | 1 week |
| Remaining 11 screens | Avg 2 days each | 3–4 weeks |
| Admin + import/export | Complex forms + file ops | 1 week |
| AI agent | Chat UI + streaming | 3 days |
| QA + parity testing | Full regression | 1 week |
| **Total** | | **~10–12 weeks** |

HTMX approach saves ~3 weeks on setup but costs ~4 weeks on grid quality and concurrency. Net: React approach is the better long-term investment.

# Hardened Migration Plan

## Context

The original plan proposes migrating a Streamlit monolith to FastAPI + HTMX. It is directionally correct but makes several proposals that conflict with what already exists in the codebase, omits critical invariants that must survive the migration, and sequences phases in a way that creates hard dependency problems. This plan corrects all of that.

Codebase snapshot:

- 202 Python files, ~12,367 lines
- 28 test files, 3,327 lines
- Domain tests are pure; service tests hit a live DB
- 16 repositories returning `RealDictCursor` plain dicts
- 18 Streamlit screens, 49 service modules, 10 domain modules
- `services/board_service.py` is the centerpiece at 716 lines

---

## Critical Errors in the Original Plan

### 1. Idempotency Guard Already Exists

`services/imports/orchestrator.py:85-110` already computes SHA-256 of `report_type + file bytes`, checks `import_batch` for an existing job with that checksum, and skips or re-runs based on status. Do not build this again. Wrap it in the new job API. Do not duplicate it.

### 2. Dead Letter Queue Already Exists

`import_batch.status` already tracks `PENDING -> PROCESSING -> COMPLETED / FAILED`. Failed imports are queryable and replayable today. Do not create a `failed_jobs` table. Expose `import_batch` via the `/health` endpoint instead.

### 3. Redis for UI Filters Is Over-Engineering

Board filters such as phase, readiness, and priority are per-user UI state. In FastAPI + HTMX, these belong in URL query params like `?phase=A&readiness=BLOCKED`, which are free, stateless, and bookmarkable. Redis is justified only for background job infrastructure in Phase 4.

### 4. Pydantic Before FastAPI Is Premature

The domain layer already uses plain dicts through typed pure functions. Adding Pydantic across 16 repositories before an API boundary exists adds churn without a consumer. Pydantic belongs at the API boundary as request and response schemas, introduced in Phase 2 alongside the routes that need it.

### 5. `version: int` Everywhere Is Premature

Payload schema versioning is appropriate only after the first breaking change. Start without it. Add it when there is an actual schema break.

### 6. Write Guard Is Session-Scoped

`services/write_guard.py` checks Streamlit session state. That is per session, not global. Disabling writes in one admin session does not block other sessions. In Phase 6, write ownership must move to the data access boundary, enforced in repositories or services, not `st.session_state`.

### 7. `HX-Refresh: 10` Is Not a Real HTMX Pattern

HTMX does not provide a built-in `HX-Refresh` response header for adaptive polling frequency. The correct pattern is to have the server return a different `hx-trigger` value in the response fragment based on job state.

### 8. Tailwind Requires an Explicit Build Decision

The current stack has no build tooling. Tailwind via CDN is acceptable only for development, not production. The plan must explicitly choose either:

- `package.json` + build step, or
- Tailwind standalone CLI binary

This must be decided before Phase 5.

---

## Invariants That Must Survive the Migration

| Invariant | Location | Risk If Violated |
|---|---|---|
| Import atomicity | `services/imports/orchestrator.py` -> `transaction()` | Partial imports corrupt turnover state |
| Idempotent board reconciliation | `services/board_reconciliation.py` | Double-mutations on every board load |
| Append-only audit tables | `lifecycle_event`, `audit_log` DB triggers | Data integrity violation |
| Domain purity | `domain/*.py` with zero I/O | Domain tests break; logic becomes untestable |
| Test suite green | `tests/domain/` and `tests/services/` | Regressions go undetected |
| Write guard at boundary | `services/write_guard.py` | Unguarded writes in multi-tenant or hybrid context |
| Connection-per-transaction | `db/connection.py:transaction()` | Autocommit state leaks across requests |

---

## Phase 0: Go / No-Go Gate

Answer these before writing code:

- Redis in prod? Ask ops. If no, delay Phase 4 and keep imports synchronous with a timeout guard.
- DB indexes? Run `\d turnover` in `psql`. Verify indexes on `(property_id)`, `(closed_at)`, and `(move_out_date)`. Add missing ones before load increases.
- Tailwind decision? Choose CDN for dev only or standalone CLI for production.
- Auth source? `LEGACY_AUTH_SOURCE=env` or `LEGACY_AUTH_SOURCE=db`. FastAPI middleware must support both.
- Nginx or Caddy available in prod? If not, the hybrid proxy strategy in Phase 6 cannot execute.

---

## Phase 1: Thread-Safe Connection Pool

Goal: replace the unsafe global singleton with a pool. No new services. No new dependencies beyond `psycopg2`.

Files to modify:

- `db/connection.py`

Implementation target:

```python
_pool: psycopg2.pool.ThreadedConnectionPool | None = None

def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(minconn=2, maxconn=10, dsn=DATABASE_URL)
    return _pool

@contextmanager
def get_connection():
    pool = _get_pool()
    t0 = time.monotonic()
    conn = pool.getconn()
    elapsed = time.monotonic() - t0
    if elapsed > 0.1:
        logger.warning("DB pool acquisition took %.0fms", elapsed * 1000)
    try:
        yield conn
    finally:
        pool.putconn(conn)
```

Critical note:

- All 16 repositories currently call `get_connection()` as a plain function.
- After this change, `get_connection()` becomes a context manager.
- Every repository must be updated to use `with get_connection() as conn:`.
- `transaction()` keeps the same purpose but must acquire and release pooled connections safely.

Verification:

- Run `pytest tests/`
- All 28 test files must pass before proceeding

---

## Phase 2: FastAPI Shell + Auth Middleware

Goal: bootable FastAPI app with one working endpoint and auth. No Streamlit changes yet.

New files:

- `api/main.py`
- `api/middleware/request_id.py`
- `api/middleware/auth.py`
- `api/deps.py`
- `api/routers/health.py`

Auth strategy:

- Move `ui/auth.py` logic into `api/middleware/auth.py`
- Middleware reads an HTTP-only signed cookie
- Validation uses existing `auth_service.py`
- Login sets an encrypted HTTP-only cookie
- Use `itsdangerous.URLSafeTimedSerializer` if available; otherwise add an explicit dependency
- Cookie payload:

```json
{"user_id": 1, "username": "name", "role": "admin", "exp": 1234567890}
```

Pydantic models introduced here only:

- `api/schemas/auth.py` with `LoginRequest`, `UserSession`
- `api/schemas/health.py` with `HealthResponse`

Verification:

- `uvicorn api.main:app --reload` starts cleanly
- `GET /health` returns `200` with pool stats
- `POST /login` sets an HTTP-only cookie and returns `200`
- `GET /health` without a valid cookie returns `401`

---

## Phase 3: Board API Endpoint

Goal: build `/api/board/{property_id}` before touching the frontend.

Files to create:

- `api/routers/board.py`
- `api/schemas/board.py`

Design rules:

1. `board_service.get_board()` already returns a list of dicts. Do not rewrite it.
2. `board_reconciliation.run_board_reconciliation_for_property()` stays inside `board_service`. Keep that behavior.
3. Board filters become URL query params.
4. `BoardRow` schema must be derived from actual `board_service` output, not invented in advance.

Draft response shape to verify against real output:

```python
class BoardRow(BaseModel):
    turnover_id: int
    unit_code: str
    phase: str
    lifecycle_phase: str
    readiness: str
    priority: str
    days_since_move_out: int | None
    days_to_move_in: int | None
    move_in_date: date | None
    task_completion: tuple[int, int]
    agreements: dict[str, str]

class BoardResponse(BaseModel):
    property_id: int
    as_of: date
    rows: list[BoardRow]
    total: int
```

Verification:

- `GET /api/board/1` returns valid JSON matching `BoardResponse`
- `GET /api/board/1?phase=A&readiness=BLOCKED` returns the filtered subset
- Run `pytest tests/`

---

## Phase 4: Import Pipeline as Background Job

Do this only if Redis is confirmed available in Phase 0.

If Redis is not available:

- Keep imports synchronous
- Wrap `orchestrator.import_report_file()` in a FastAPI route with a 60-second timeout guard
- Return the existing `import_batch.batch_id`
- Poll `/api/imports/{batch_id}/status`

If Redis is available:

New dependency:

- `rq`

New files:

- `api/routers/imports.py`
- `api/workers/import_worker.py`

What does not change:

- `services/imports/orchestrator.py` stays unchanged
- `import_batch` remains the existing DLQ surface
- Existing SHA-256 idempotency logic stays in the orchestrator

`/health` update:

- Add `queue_depth` from RQ queue length

Verification:

- Upload CSV to `POST /api/imports/upload` and receive `batch_id`
- Poll `GET /api/imports/{batch_id}/status`
- See state transition `PENDING -> PROCESSING -> COMPLETED`
- Upload the same file again and get the existing completed batch with no duplicate processing
- Upload a corrupt file and confirm `FAILED` state plus stored error context

---

## Phase 5: HTMX Frontend, Board Screen First

Goal: replace the Streamlit board screen first. Streamlit remains active for all other screens.

Tailwind decision:

- Use the standalone Tailwind CLI binary
- Dev command:

```bash
tailwindcss -i input.css -o static/tailwind.css --watch
```

- Build once for prod
- Add built CSS artifacts to `.gitignore`
- Do not add `npm`

New files:

- `api/templates/base.html`
- `api/templates/board.html`
- `api/templates/board_row.html`
- `api/routers/pages.py`

HTMX patterns:

- Board load:

```html
hx-get="/api/board/{property_id}" hx-trigger="load" hx-target="#board-table"
```

- Filters:

```html
hx-get="..." hx-include="..."
```

- Job polling:

```html
hx-get="/api/imports/{batch_id}/status" hx-trigger="every 2s"
```

- Server returns a fragment with a different `hx-trigger` when the job has been running long enough to slow polling

Template rule:

- Templates render data only
- Routes call services
- Templates call no Python directly

Proxy routing:

```nginx
location /board { proxy_pass http://fastapi:8001; }
location /api/  { proxy_pass http://fastapi:8001; }
location /      { proxy_pass http://streamlit:8501; }
```

Verification:

- `/board/{property_id}` renders correctly
- Filter changes update only the table
- Streamlit still works for all remaining screens
- Run `pytest tests/`

---

## Phase 6: Screen-by-Screen Cutover

### Strategic fork

- **Path A (HTMX hybrid, above):** Phase 5 ships the board as Jinja + HTMX. Phase 6 migrates additional routes behind Nginx while Streamlit covers unmigrated screens.
- **Path B (React SPA):** Skip HTMX board templates. FastAPI serves JSON under `/api/*` and the Vite build from `/` (`StaticFiles(..., html=True)`). React Router owns all URLs below. Remove `api/routers/pages.py`, `api/templates/`, and root Tailwind/static artifacts once React owns styling inside `frontend/`.

Path B does **not** invalidate Phase 0–4 or the board API from Phase 3; it replaces Phase 5’s template surface and widens Phase 1’s API scope to match the JSON contract the React app needs (see terminal plan: properties, turnovers, tasks, notes, schedule, morning, risk, exports, imports, admin, validator, AI).

### Path A — proxy migration order (HTMX)

1. `/health`
2. `/board`
3. `/import`
4. `/unit/{turnover_id}`
5. `/admin`
6. `/exports`
7. Remaining screens (use Path B table below as the implementation checklist for parity)

### Path B — Phase 6 remaining screens (easiest → hardest)

Implement after the **core shell** (login, sidebar, property context, `/board/:propertyId`, `/unit/:turnoverId`) is done in React.

| Order | Screen | Key UI | Notes |
|------:|--------|--------|--------|
| 1 | Risk Radar | Read-only table | Client-side filter; sort by `risk_score` |
| 2 | Property Structure | Nested accordion | Read-only hierarchy |
| 3 | Flag Bridge | AG Grid read-only | Row click → unit detail |
| 4 | Morning Workflow | Dashboard cards + inline date edit | Top actions set board filter + navigate to board |
| 5 | Operations Schedule | AG Grid editable (manager) / read-only table (vendor) | Batch save for manager |
| 6 | Add Turnover | Cascading selects | Phase → building → unit |
| 7 | Export Reports | Prepare + downloads | If prepare is async: poll job status (e.g. React Query interval) |
| 8 | Import Console | Multi-tab file upload | Poll `import_batch` (or job) status |
| 9 | Import Reports | Three-tab correction flow | Overrides + invalid data + diagnostics |
| 10 | Work Order Validator | Upload + classified exports | Align with Streamlit validator tabs |
| 11 | Admin | Four-tab control plane | DB writes toggle, phase scope, unit master import, app users |
| 12 | AI Agent | Chat | SSE / `EventSource` for streamed replies |

**Path B route map (React Router)** — mirror Streamlit nav groups:

| Route | Page |
|-------|------|
| `/login` | Login |
| `/board/:propertyId` | Board |
| `/unit/:turnoverId` | Unit detail |
| `/schedule/:propertyId` | Operations schedule |
| `/morning/:propertyId` | Morning workflow |
| `/flags/:propertyId` | Flag Bridge |
| `/risk/:propertyId` | Risk Radar |
| `/import/:propertyId` | Import console |
| `/import-reports/:propertyId` | Import reports |
| `/exports/:propertyId` | Export reports |
| `/validator` | Work order validator |
| `/admin` | Admin |
| `/add-turnover/:propertyId` | Add turnover |
| `/structure/:propertyId` | Property structure |
| `/ai` | AI agent |

**Path B API prerequisites** (complete or stub before building each row in the table): properties + cascading selects, board + sidebar flags, turnover CRUD + audit, tasks PATCH, notes, schedule batch, morning aggregate, risk rows, export prepare/status/download, import upload/history/correction endpoints, admin writes + users + phase scope + unit master, validator job + download, AI sessions + SSE messages.

Corrected write ownership rule:

```python
if request_source == "streamlit":
    raise WriteOwnershipError("This domain is now managed by FastAPI")
```

Use `X-Request-Source: streamlit | fastapi`.

Services enforce this rule. Do not rely on `st.session_state`.

Rollback strategy:

- Nginx config is the rollback switch
- To roll back a screen, remove its FastAPI location block
- Keep Streamlit alive through Phase 6
- Do not decommission Streamlit while any migrated screen is unverified

---

## Phase 7: Decommission Streamlit

Do this only when:

- All Streamlit-parity screens are verified in the chosen frontend (HTMX routes and/or React SPA)
- `pytest tests/` is green
- No `proxy_pass http://streamlit` blocks remain in Nginx (Path A), or Streamlit is not deployed (Path B)

Steps:

1. Remove the Streamlit process from the process manager
2. Remove `streamlit` and `st.*` imports
3. Archive or remove the `ui/` directory (archive first if you want a reference copy)
4. **Path B only:** remove `api/routers/pages.py`, `api/templates/`, and HTMX-only static or root Tailwind inputs if superseded by `frontend/`
5. Remove Streamlit secret resolution from `config/settings.py` where no longer needed
6. Run `pytest tests/` again

---

## Top 5 Guardrails

| Guardrail | Implementation | What It Prevents |
|---|---|---|
| Import atomicity preserved | `orchestrator.py -> transaction()` stays intact | Partial import corruption |
| Idempotency reused, not rebuilt | Existing SHA-256 + `import_batch` check exposed via API | Double-processing corruption |
| Write ownership at service layer | `X-Request-Source` enforcement in services | Streamlit and FastAPI both writing same domain |
| Rollback is proxy config change | Keep Streamlit alive through Phase 6 | Unrecoverable frontend regression |
| Test suite is the migration contract | `pytest tests/` after every phase | Silent logic regressions |

---

## Corrected Dependency Order

```text
Phase 0 (Prerequisites)
  └─ Phase 1 (Connection Pool)
       └─ Phase 2 (FastAPI + Auth)
            ├─ Phase 3 (Board API)
            │    └─ Phase 5 (Frontend: Path A = HTMX board, Path B = React shell + board)
            │         └─ Phase 6 (Remaining screens — Path B uses ordered table in §Phase 6)
            │              └─ Phase 7 (Decommission Streamlit; Path B also removes HTMX/templates)
            └─ Phase 4 (Background Jobs) — requires Phase 0 Redis gate
```

---

## Verification Checklist

- `pytest tests/` is green after Phase 1
- `pytest tests/` is green after Phase 2
- `GET /api/board/1` matches `board_service.get_board()` output exactly
- Import upload produces the same DB state as the current Streamlit flow
- Duplicate file upload returns the existing batch with no new turnover or task rows
- HTMX board output matches Streamlit board for the same property
- Removing the FastAPI location block restores Streamlit for that screen
- `/health` shows pool stats, Redis depth if applicable, and `import_batch` failure count

---

## Files Critical to the Migration

| File | Lines | Role |
|---|---:|---|
| `db/connection.py` | 53 | Full rewrite in Phase 1 |
| `db/repository/*.py` | 16 files | Mechanical update in Phase 1 |
| `services/imports/orchestrator.py` | 245 | Preserved and called by the Phase 4 worker |
| `services/board_service.py` | 716 | Preserved and called by the Phase 3 route |
| `services/board_reconciliation.py` | 98 | Preserved inside `board_service` |
| `ui/auth.py` | 117 | Logic migrates to `api/middleware/auth.py` in Phase 2 |
| `config/settings.py` | 42 | Keep env var resolution; remove Streamlit secrets in Phase 7 |
| `tests/` | 28 files | The migration contract |

---

## Approved Changes From the Original Plan

### Eight errors corrected

1. Idempotency guard already exists in `orchestrator.py`
2. `import_batch` with `FAILED` status is already the DLQ
3. Redis is not for UI filters; URL query params handle those
4. Pydantic belongs at the API boundary, introduced per phase
5. `version: int` is added only at first schema breakage
6. `write_guard.py` is per Streamlit session, not global
7. `HX-Refresh` is not a real HTMX solution for adaptive polling
8. Tailwind build strategy is explicitly chosen: standalone CLI, no `npm`

### Critical additions

- Phase 0 go / no-go gate before coding
- Invariant table with locations and failure modes
- Rollback strategy using Nginx while Streamlit stays alive
- Corrected dependency graph with Redis gating Phase 4
- Test suite defined as the migration contract

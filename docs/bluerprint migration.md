

> Working migration guardrails live in [docs/specs/MIGRATION_HARDENING_PLAN.md](docs/specs/MIGRATION_HARDENING_PLAN.md). Use that document for approved corrections, Phase 0 gates, invariants, rollback, and test-contract rules before writing migration code.

## Brief context: where things stand and why we’re migrating

**What you have now**

- A single **Streamlit + PostgreSQL** app: one process that serves the UI and does all work (imports, board load, reconciliation, backfill) in the request. DB is one global connection; auth is optional username/password in memory; config/secrets come from env or a file. There’s no React/FastAPI, no queue, no Redis, no API layer, no Terraform, no CI/CD, and no observability. The “AI” screen is a stub with no LLM. Long-running work blocks the UI; there’s no worker or cache.

**Why migrate**

- To get to a **production-ready** system: safe secrets, real auth, no blocking requests, scalable reads (cache) and writes (queue + workers), a proper API and frontend, infra as code, and full observability. The current stack can’t support that without a structural change.

**From here on**

- The rest of this answer describes **only the target system**—the one we’re building step by step with checkpoints. No further reference to the old implementation.

---

## 1. System goal (what this system does)

- **Core job:** Act as the **operational sync and execution layer** for apartment turnover: ingest PMS report data (files), keep turnover state aligned with those reports, and support daily workflows (board, readiness, SLA, repairs). It is **not** the PMS, accounting, or leasing system.
- **Main workflows:**
  - **Ingest:** Accept report uploads → enqueue jobs → workers validate and apply rules → update batches, rows, turnovers, tasks, audit. API returns immediately with a job id.
  - **Board (and related views):** Serve read-optimized board data (turnovers, units, tasks, readiness, SLA, priority) from cache or DB, with filters. No heavy reconciliation in the request path; that runs in workers after imports or on schedule.
  - **Detail and edits:** Serve unit/turnover detail; accept edits (validated at API); quick writes in API or small jobs; heavy/bulk updates via queue.
  - **Scheduled automation:** “Midnight”-style automation (e.g. On Notice → Vacant Not Ready, create turnovers from snapshots) runs only as queue jobs consumed by workers.
  - **Admin:** Property/phase setup, toggles (e.g. DB writes), unit and task-template management, all via API.
  - **AI assistant:** User sends a message → API enqueues an AI job → worker calls LLM with allowed context → result stored/served async. No LLM calls in the API process.

---

## 2. Users (who uses it, through what interface)

- **Operator:** Uses the **web app** daily: board, unit detail, morning workflow, flag bridge, risk radar, light imports. Authenticates via Supabase Auth; all actions through the API with JWT.
- **Admin:** Uses the **same web app** with access to admin surfaces: property/phase config, DB-writes toggle, unit/task-template management, repair/diagnostics. Same auth and API.
- **System:** Scheduler and **workers**; no UI. Triggered by queues (and optionally cron/EventBridge). Identity via IAM or app credentials; no end-user JWT.
- **Interface:** Primary interface is the **React (Vite, TypeScript, Tailwind) SPA** on S3 + CloudFront. All data and actions go through the **API** (FastAPI behind API Gateway). Optional future: machine-to-machine API with keys and scopes.

---

## 3. Inputs (what data comes in, from where, format)

- **From users (web app):**
  - **Auth:** Email + password (and/or OAuth) → Supabase Auth; no business logic in our API.
  - **Property selection:** Property id (from API-supplied list); validated for access (API or RLS).
  - **Import:** Report type (enum: MOVE_OUTS, PENDING_MOVE_INS, AVAILABLE_UNITS, PENDING_FAS), file (CSV or xlsx), max size (e.g. 10 MB). Multipart or presigned upload + metadata.
  - **Board/filters:** Property id, optional phase ids, priority, readiness, assignee, flag category. Enums and ids validated at API.
  - **Unit/turnover edits:** Turnover/task ids + payload (e.g. status, dates, assignee). Validated against schema and access.
  - **Admin:** Property name, phase scope (list of phase ids), toggles (e.g. boolean). Validated at API.
  - **AI:** Session id (or null), message text. Length and rate limits enforced.
- **Format:** JSON for REST bodies; multipart for file upload; query params for filters/pagination. All validated (types, required fields, enums, ranges, size) before use; invalid → 400.
- **External data sources:** User-uploaded PMS files only. Supabase (Postgres, Auth, optional Storage) and AI provider (called only by workers) are integrations, not “inputs” in the product sense.

---

## 4. Outputs (what it produces, stores, sends, displays)

- **To users (UI):** Auth tokens and user info after sign-in; JSON for board, detail, metrics, import job status, AI replies; error payloads (4xx/5xx) with clear structure.
- **Stored:** In **Supabase Postgres** (with RLS): properties, phases, buildings, units, turnovers, tasks, notes, risks, SLA events, audit log, import batches/rows, snapshots, phase scope, system settings. Optionally **Supabase Storage** for original import files. **Redis** for cache (board/metrics) and rate-limit state; TTLs and invalidation on writes.
- **Async (queue → worker):** Import job result (DB + cache invalidation); midnight automation (transitions and new turnovers); AI completion (LLM response stored/served). No user response body from workers; clients poll or get push for job result.
- **External calls:** Workers call **LLM provider** (e.g. OpenAI); API and workers call **Supabase** and **Redis**. API enqueues to **SQS**; workers consume from SQS.

---

## 5. Integrations (APIs, DBs, files, queues, auth, cloud)

- **Frontend:** React (Vite, TypeScript strict, Tailwind). Hosted on **AWS S3 + CloudFront** (or Amplify). HTTPS only.
- **API:** **FastAPI** (async, Docker). Behind **API Gateway** (or ALB). No long-running or AI work in request path.
- **Compute:** **App Runner** (short term) for API; migration path to **ECS** for API and workers. **Workers** as separate container(s), consuming **SQS**.
- **Data:** **Supabase** — Postgres (RLS on), Auth (JWT), optional Storage. Connection strings and keys from **AWS Secrets Manager** at runtime.
- **Async:** **SQS** — queues for import, midnight automation, AI jobs; DLQ and retries defined. Workers only pull from SQS.
- **Caching:** **Redis** (e.g. Elasticache) — board/metrics cache, rate limiting. Invalidation on relevant writes.
- **Observability:** **CloudWatch** (logs, metrics), **X-Ray or OpenTelemetry** (tracing), **alerts** (failure, latency, cost). All wired in infra.
- **CI/CD:** **GitHub Actions** — test, build images, deploy to dev/staging/prod; secrets and env per environment.
- **Secrets:** **AWS Secrets Manager** only; injected at runtime into API and worker containers. Not in code or images.

---

## 6. Constraints (language, framework, hosting, security, latency, budget, deadlines)

- **Frontend:** Strict TypeScript; no `any` for core flows. Typed API contracts.
- **Backend:** FastAPI, async-first; no blocking calls in request path. DB/Redis via async or bounded thread pool.
- **API:** No long-running work in handlers. Imports, AI, and heavy automation are enqueued; handlers return quickly (e.g. 202 + job id).
- **AI:** All LLM calls in workers; API never calls the LLM.
- **Auth:** JWT (Supabase) required on every API request (except health); validated at gateway or FastAPI.
- **Data:** RLS enabled and enforced in Supabase Postgres.
- **Infra:** Fully defined in **Terraform** (gateway, compute, SQS, Redis, secrets, observability). No critical resources only in console.
- **Network:** HTTPS only; CORS restricted to frontend origin(s).
- **Rate limiting:** At API Gateway and/or in-app with Redis.
- **Latency/budget/deadlines:** Not specified here; to be set when you define the concrete spec (e.g. P95 latency, cost cap, go-live date).

---

## 7. Success criteria (when this is “done”)

- **API never blocks on AI or long tasks** — all such work is queued and processed by workers.
- **Queue + worker system is live** — SQS and workers deployed; import, midnight, and AI jobs are consumed and complete (or go to DLQ with alerts).
- **Redis is used** — expensive/repeated reads (e.g. board) are cached; cache is invalidated on writes.
- **API Gateway (or ALB) is the only public entry** — all production traffic goes through it with TLS.
- **Secrets only from Secrets Manager** — none in code or Docker images.
- **Structured, searchable logs** — JSON, with trace id; queryable in CloudWatch.
- **Tracing** — request and job traces with spans for DB, Redis, external calls.
- **Alerts** — configured for failures, latency SLOs, and cost spikes.
- **Environments** — dev, staging, prod isolated (separate DBs, queues, Redis, credentials).
- **CI/CD** — deploy is automated from pipeline; no manual deploy steps.
- **Scaling** — workers can scale independently of the API.




# PRODUCTION-READINESS GAP ANALYSIS

## 1. ARCHITECTURE GAPS

- **Frontend:** No React, no Vite, no TypeScript, no Tailwind. App is **Streamlit** (`app.py`, `ui/screens/*.py`). Target “React (Vite + TypeScript strict + Tailwind)” is **fully missing**.
- **Backend:** No FastAPI. No HTTP API layer. Streamlit talks to DB via `db/connection` and services. Target “FastAPI (Dockerized)” is **fully missing**.
- **Hosting:** No Amplify, S3, or CloudFront. No frontend deploy config. Target “AWS (Amplify or S3 + CloudFront)” is **missing**.
- **API entry:** No API Gateway, no ALB in front of any service. Streamlit is the only entry; no separate API to put behind a gateway.
- **Queue:** No SQS or any queue. `scripts/run_midnight_automation.py` and import pipeline run **in-process** (cron + Streamlit upload). Target “SQS + worker” is **missing**.
- **Worker:** No background worker service. Midnight automation and heavy imports run in the same process (script or Streamlit). Target “Worker service (background processing)” is **missing**.
- **Caching:** No Redis. Caching is **Streamlit in-memory** only (`st.cache_data(ttl=30|60)`). No shared cache, no rate limiting store. Target “Redis (caching + rate limiting)” is **missing**.
- **CI/CD:** No `.github/workflows` or other pipeline. No automated test/deploy. Target “CI/CD (GitHub Actions)” is **missing**.
- **Observability:** No structured JSON logs, no tracing (X-Ray/OpenTelemetry), no alerting config. Target “Observability (logs, tracing, alerts)” is **missing**.
- **Infrastructure as code:** No `.tf` files. No Terraform. Target “Terraform (ALL AWS resources)” is **missing**.
- **Supabase:** DB is **plain PostgreSQL** via `DATABASE_URL` and `psycopg2`. `SUPABASE_URL`/`SUPABASE_KEY` exist in `config/settings.py` but are **unused** for connection or Auth. Supabase Auth and Storage are **not integrated**. Target “Supabase (Postgres + Auth + Storage)” is **not met** (Postgres-only, no Supabase Auth/Storage).

---

## 2. BACKEND (FastAPI)

- **No FastAPI.** There is no FastAPI app. “Backend” is Streamlit + services + `db/connection`. All “backend” findings below apply to this stack.
- **Blocking DB:** All DB access is **synchronous** (`psycopg2`, `get_connection()`). Every board load, import, and script blocks the process. Under load, Streamlit requests and cron will block each other; no async handling.
- **Single global connection:** `db/connection.py` uses one global `_connection`. No connection pool. Under concurrency (multiple Streamlit sessions or script + app), one connection is shared; risk of connection exhaustion, errors, or serialization of all DB work.
- **Validation:** No Pydantic/request validation (no API). Input validation is ad hoc in services (e.g. import schema validators). No central request/response validation.
- **Token verification:** No JWT or API tokens. Auth is session-only (`ui/auth.py`: `st.session_state.authenticated`) and optional `APP_USERNAME`/`APP_PASSWORD`. If both are unset, `require_auth()` bypasses login. No Supabase Auth, no token verification.
- **Security:** Write guard is enforced only in Streamlit context; in CLI/scripts (`get_script_run_ctx() is None`) writes are **always allowed**. Midnight script can write even when “DB Writes” is off in Admin. No CSRF/XSRF in app code (Streamlit default only). No rate limiting.

---

## 3. FRONTEND

- **Not a SPA:** “Frontend” is Streamlit; no React, no client-side routing, no TypeScript. State and API handling below are for this UI.
- **State:** State is `st.session_state` (in-memory, server-side). No persistence across restarts; no Supabase Auth state. Session can be lost on redeploy or server restart.
- **API handling:** No REST client. Data comes from service calls in the same process (e.g. `board_service.get_board_view`, `import_service.run_import_pipeline`). Large imports run **synchronously** in the Streamlit run; user waits and can hit timeouts or browser disconnect.
- **Auth flow:** Login is username/password vs env/secrets only; no OAuth, no Supabase Auth, no MFA. Credentials in `APP_USERNAME`/`APP_PASSWORD`; if empty, auth is skipped. No token refresh, no session expiry.
- **Error handling:** Exceptions in import/board show generic `st.error(str(exc))` or are swallowed (e.g. `get_board()` wraps reconciliation in `try/except: pass`). No global error boundary, no retry UX, no distinction between transient and permanent failures.

---

## 4. DATABASE & AUTH (Supabase)

- **RLS:** Schema has **no** `ENABLE ROW LEVEL SECURITY` and **no** `CREATE POLICY`. All access is with the same DB role; any user with DB credentials sees all rows. If you later switch to Supabase and multi-tenant, data is not protected by RLS.
- **Queries:** Repositories use parameterized queries (`%s`). No raw string concatenation of user input into SQL. **PASS** on SQL injection for current usage.
- **Indexes:** Indexes exist for main access patterns (e.g. `turnover_property_open_idx`, `task_turnover_idx`, `import_row_batch_idx`). No obvious missing index for the current query set.
- **Auth misuse:** Supabase Auth is not used. `SUPABASE_URL`/`SUPABASE_KEY` are loaded but unused. DB is accessed with a single credential (`DATABASE_URL`); no per-user or per-tenant DB identity.

---

## 5. INFRASTRUCTURE

- **Terraform:** No Terraform. No `.tf` files. No AWS resources defined as code.
- **Environments:** No dev/staging/prod separation in code or config. Single `DATABASE_URL` and optional `APP_USERNAME`/`APP_PASSWORD`. No env-specific Terraform workspaces or config.
- **Deploy:** No Dockerfile, no App Runner, no ECS/EKS. No defined runtime or scaling.

---

## 6. SECURITY RISKS

- **Secrets:** `config/settings.py` reads from `os.getenv()` then `st.secrets`. `.streamlit/secrets.toml` contains `DATABASE_URL = "postgresql://localhost/dmrb"`. Root `.gitignore` was not found (only `.pytest_cache/.gitignore`). If repo root has no `.gitignore` or secrets not ignored, **secrets.toml can be committed** and leak DB URL and any future secrets.
- **Rate limiting:** None. No Redis or in-app throttle. A single client can hammer the Streamlit app or scripts and exhaust resources.
- **Auth:** Weak. Optional basic username/password; when unset, no login. No Supabase Auth, no JWT, no session expiry. Session is in-memory only.
- **CORS:** No custom CORS in app code. Streamlit’s default applies; no API to attach CORS to. If you add an API later without restricting origins, you risk open CORS.

---

## 7. PERFORMANCE & SCALING RISKS

- **No Redis:** No shared cache. Board/import data is only in Streamlit’s in-memory cache (per process). Multiple instances don’t share cache; DB load and latency stay high under traffic.
- **No queue:** Heavy work (import, midnight automation) is not offloaded. Import runs in the Streamlit process; midnight runs in a script. Under load, long-running work will block and can time out or fail without retry.
- **Long-running requests:** Board load runs `reconcile_open_turnovers_from_latest_available_units`, `ensure_on_notice_turnovers_for_property`, and `backfill_tasks_for_property` then builds the board. Import runs the full pipeline in one request. Both can exceed browser/Streamlit timeouts and cause silent or visible failures.
- **N+1 in board:** `get_board()` (e.g. `board_service.py` ~296–301) does: 1 query for turnovers, 1 for units, then **per turnover** `task_repository.get_by_turnover`, `risk_repository.get_open_by_turnover`, `note_repository.get_by_turnover`. So **1 + 1 + 3×N** queries. With hundreds of turnovers, this will be slow and can time out or overload DB.

---

## 8. OBSERVABILITY GAPS

- **Logs:** Some services use `logging.getLogger(__name__)` and `logger.exception`/`logger.warning`. Logs are **not structured (JSON)**. No request/session/trace IDs. In production, correlating logs across services and requests is hard.
- **Tracing:** No OpenTelemetry, no X-Ray. No distributed or request-level tracing. Debugging cross-service and DB latency is guesswork.
- **Alerts:** No alerting config (no PagerDuty, SNS, etc.). Failures and degradation can go unnoticed.

---

## 9. FAILURE POINTS

- **Board load under load:** Many open turnovers → N+1 queries + reconciliation/backfill. Single connection, blocking I/O. Result: slow responses, timeouts, or Streamlit/connection errors. Exceptions in reconciliation are swallowed (`try/except: pass`), so **silent partial failures** (e.g. stale or missing backfill) with no alert.
- **Import in UI:** Large file runs in-process. Can hit Streamlit/HTTP timeouts; user sees generic error. No retry, no job queue; duplicate or partial state possible if user retries.
- **Midnight script:** No queue, no retries. If script fails (DB, OOM, crash), run is lost until next cron. No dead-letter, no visibility.
- **DB connection:** Single global connection. If it drops (network, Supabase restart), all operations fail until restart. No reconnect or health check on reuse.
- **Secrets in file:** If `secrets.toml` is committed, anyone with repo access gets DB and app credentials; full DB and app compromise.

---

## 10. PRIORITIZED FIX LIST

**P0 (must fix before production)**

1. **Secrets:** Ensure `.streamlit/secrets.toml` (and any file with secrets) is in `.gitignore` and never committed; use env or a secrets manager at runtime.
2. **Auth:** Require auth (no bypass when `APP_USERNAME`/`APP_PASSWORD` unset) or integrate Supabase Auth and enforce it on every sensitive path.
3. **DB connection:** Replace single global connection with a connection pool (e.g. `psycopg2.pool`) or Supabase-backed pool; add reconnect/health check so one bad connection doesn’t take down the app.
4. **Long-running work:** Offload import and midnight automation to a queue (e.g. SQS) + worker so Streamlit and cron don’t block or timeout; add retries and clear failure visibility.
5. **RLS (if multi-tenant/Supabase):** Add RLS and policies before exposing Supabase or multi-tenant data; otherwise one credential exposes all data.

**P1 (should fix soon)**

6. **N+1 on board:** Batch-load tasks, risks, notes by turnover IDs (e.g. one query per entity type with `WHERE turnover_id = ANY(%s)`) instead of per-turnover calls in `get_board()`.
7. **Observability:** Introduce structured (JSON) logs with request/session/correlation IDs; add tracing (e.g. OpenTelemetry/X-Ray) and at least one alert channel for errors and latency.
8. **Write guard:** Apply the same “DB writes on/off” behavior in CLI/scripts as in the UI (e.g. read `system_settings` or env) so midnight script respects the same guard.
9. **Error handling:** Replace broad `except: pass` in board load with logged, categorized handling and optional user-visible “degraded” state instead of silent wrong data.

**P2 (improvements)**

10. **API + gateway:** Introduce FastAPI (or similar) behind ALB/API Gateway for future mobile/API clients; add rate limiting (e.g. with Redis).
11. **Redis:** Add Redis for shared cache and rate limiting to reduce DB load and abuse.
12. **Align with target stack:** React (Vite + TS + Tailwind) frontend, FastAPI backend, Terraform, CI/CD, and Supabase Auth/Storage as per your target architecture.

---

# CRITICAL SYSTEM VALIDATION (MANDATORY)

**1. ASYNC PROCESSING**  
- **FAIL.** No SQS or equivalent. Long-running and “AI” work is not offloaded.  
- **Where it blocks:** Import in `ui/screens/import_console.py` (upload → `import_service.run_import_pipeline` in-process). Midnight in `scripts/run_midnight_automation.py` runs in one process. Both can block and timeout; no worker, no retry.

**2. CACHING**  
- **FAIL.** No Redis. Only Streamlit in-memory `st.cache_data` (TTL 30/60s).  
- **Impact:** Repeated board/import views and multiple instances hit DB every time after TTL; no shared cache, higher DB load and latency. No Redis-based rate limiting.

**3. API ENTRY LAYER**  
- **FAIL.** No API Gateway or ALB in front of a backend API. Streamlit is the only entry.  
- **Impact:** No central place for TLS termination, rate limiting, or auth at the edge; exposure and abuse risk.

**4. RUNTIME SECRETS**  
- **FAIL.** Secrets come from `os.getenv()` or `st.secrets` (backed by `secrets.toml` on disk). Not injected by a secret manager at runtime; rotation is manual and file-based.  
- **Impact:** If `secrets.toml` is ever committed or the server is compromised, credentials are exposed; no automatic rotation story.

**5. OBSERVABILITY DEPTH**  
- **FAIL.** Logs are plain text, not JSON; no tracing; no alerts.  
- **Impact:** Production debugging is hard; no request correlation, no latency breakdown, no automatic notification on failures.

**6. ENVIRONMENT ISOLATION**  
- **FAIL.** No separate dev/staging/prod config or resources. Single DB and app config.  
- **Impact:** Deploys and experiments hit the same data; risk of data loss and failed deploys affecting production.

**7. SCALING LIMITATIONS**  
- **FAIL.** No App Runner/ECS/EKS; no container or scaling config. No defined path from “short term” to ECS/EKS.  
- **Impact:** Scaling is undefined; under load the single-process Streamlit + single DB connection will be the bottleneck and single point of failure.

---

**Summary:** The codebase is a **Streamlit + PostgreSQL monolith** with no React, no FastAPI, no Terraform, no queue, no Redis, no CI/CD, and no observability. It does not match the target architecture. To reach production readiness, address P0 first (secrets, auth, DB connection, offloading long-running work, and RLS if applicable), then P1 (N+1, observability, write guard, errors), then P2 (API, Redis, and full alignment with the target stack).




# SYSTEM DEFINITION (FROM CODE)

## SYSTEM GOAL

**What it does end-to-end**

- **Problem:** Keeps apartment turnover state in sync with PMS reports and supports day-to-day operations (board, readiness, SLA, repairs). It is not the PMS, accounting, or leasing system.
- **Workflows:**
  1. **Ingest:** User uploads PMS CSV (or xlsx) for one of four report types → checksum → schema check → parse → per-row validation/conflict handling → batch written to DB; turnovers/tasks/audit updated per report rules.
  2. **Board:** User picks property → app loads open turnovers, units, tasks, risks, notes → reconciles from latest Available Units, ensures on-notice turnovers, backfills tasks → computes lifecycle/readiness/SLA/agreements/priority → renders filterable board (and Flag Bridge, Risk Radar, Morning Workflow from same data).
  3. **Unit/turnover detail:** User selects a turnover → detail view with tasks, notes, readiness; inline edits (task status, dates, etc.) when DB writes are enabled.
  4. **Admin:** Property CRUD, phase scope, DB-writes toggle (persisted in `system_settings`), unit master import, task template management.
  5. **Import automation (out-of-app):** Cron runs `scripts/run_midnight_automation.py` → for each property, transitions On Notice → Vacant Not Ready by `available_date`, creates turnovers from `unit_on_notice_snapshot` where `available_date <= today`; no queue, runs in one process.
  6. **Repair/diagnostics:** Import Reports and Repair Reports screens show non-OK import rows, conflicts, missing move-outs, etc.; user can fix data or re-import.
  7. **Export/Work order validator / Operations schedule:** UI surfaces exist; export generation and full behavior are not implemented in the reviewed code paths.

**AI**

- **Where:** Only the “DMRB AI Agent” screen (`ui/screens/ai_agent.py`).
- **Reality:** Docstring: “Placeholder data only — no LLM API wired yet.” Replies are hardcoded: “(No API connected — placeholder reply.)” and “(No API connected — your message was received.)”. No OpenAI/Anthropic or other LLM calls in the codebase.
- **Conclusion:** AI is not used; the screen is a stub.

---

## USERS

- **Who:** One effective role: anyone who can open the app. No role or permission checks in code beyond “can I see the app” (auth gate).
- **How they interact:** Web app only. Streamlit server; users use the browser. No REST/API for external clients. CLI only for `run_midnight_automation.py` (and similar scripts).
- **Authentication:** Implemented in `ui/auth.py`:
  - If `APP_USERNAME` or `APP_PASSWORD` is set (env or `st.secrets`): login form; success sets `st.session_state.authenticated = True`.
  - If both are unset: `require_auth()` sets `authenticated = True` and returns; no login.
  - No Supabase Auth, no JWT, no OAuth, no session expiry. Auth is in-memory session state only.

---

## INPUTS

| Source | Format | Validation |
|--------|--------|------------|
| **Login** | Form: username, password (plain text) | Compared to `APP_USERNAME`/`APP_PASSWORD`; no rate limit, no lockout. |
| **Property selection** | Sidebar selectbox → `st.session_state.property_id` | From `property_service.get_all_properties()`; no server-side check that user may access that property. |
| **Import files** | CSV or xlsx upload; in-memory bytes then temp file for orchestrator | File: `validate_import_file` (file_validator); schema: `validate_import_schema` (required columns per report type, skiprows). No max file size; no row limit beyond processing in one go. |
| **Report type** | Fixed set: MOVE_OUTS, PENDING_MOVE_INS, AVAILABLE_UNITS, PENDING_FAS | Orchestrator routing; unknown type → “No handler” and batch failed. |
| **Board/Flag filters** | Session state: priority, phase, readiness, assignee, “flag category” | From UI; filter applied in Python on already-loaded board list. |
| **Unit/turnover edits** | Forms / data_editor: task status, dates, assignee, turnover dates, etc. | Service/DB layer; write_guard checks “DB writes” toggle when in Streamlit context. |
| **Admin** | New property name, phase scope selection, DB writes checkbox, unit/task template edits | Persisted via services; no schema validation beyond DB. |
| **Midnight script** | CLI: optional `--date YYYY-MM-DD` | Parsed as date; invalid format → script exits 1. |
| **Config** | Env vars and/or `.streamlit/secrets.toml` | `get_setting()`: env wins, then st.secrets. No validation of DATABASE_URL format or required keys. |

There are no API request payloads (no public API). No external event or webhook inputs in code.

---

## OUTPUTS

- **UI:** Streamlit pages (board, flag bridge, risk radar, morning workflow, unit detail, import/repair/export screens, admin, AI agent stub). Responses are server-rendered HTML/WebSocket (Streamlit); no separate JSON API for the app.
- **Stored data:** PostgreSQL via `db/connection` and repositories. Tables: property, phase, building, unit, turnover, task_template, task, note, risk_flag, sla_event, audit_log, import_batch, import_row, turnover_task_override, unit_movings, unit_on_notice_snapshot, phase_scope, system_settings, etc. Writes go through services; many paths call `check_writes_enabled()` (when in Streamlit).
- **External calls:** None. No outbound HTTP to AI providers, webhooks, or third-party APIs in the codebase.
- **Background jobs:** No queue or worker. The only “background” behavior is the cron-driven script `run_midnight_automation.py`, which runs in a single process and is not part of the web app. Import runs synchronously in the Streamlit request that handles the upload.

---

## INTEGRATIONS

**Present in code**

- **PostgreSQL:** Single connection via `DATABASE_URL` and `psycopg2`; `prepare_threshold=None`. No Supabase client used for DB.
- **Supabase:** `SUPABASE_URL` and `SUPABASE_KEY` are read in `config/settings.py` and never used elsewhere. No Supabase Auth, Storage, or Realtime.

**Not present (required for your target production)**

- **SQS (queue):** Not used. Import and midnight automation are synchronous/in-process.
- **Redis (cache):** Not used. Only Streamlit in-memory cache (`st.cache_data` TTL 30/60s).
- **API Gateway (or ALB):** No API layer in front of the app; Streamlit is the only entry.
- **AWS (App Runner, S3, CloudFront, etc.):** No AWS resources or SDK usage in the repo.
- **AI providers:** No integration; AI Agent is a stub.

---

## CONSTRAINTS (INFERRED FROM CODE)

**Tech stack (actual)**

- **Frontend:** Streamlit (Python). No React, no TypeScript, no Tailwind.
- **Backend:** No FastAPI. Application process is Streamlit + services + `db/connection`; no separate API server.
- **Data:** PostgreSQL via `psycopg2` and `DATABASE_URL`. Supabase is only in config, not in use.
- **Deploy:** No Dockerfile, no Terraform, no AWS/App Runner config in repo.

**Security**

- **JWT:** None. Auth is session-state + optional username/password.
- **RLS:** Not used. Schema has no `ENABLE ROW LEVEL SECURITY` or policies; one DB credential sees all data.
- **Secrets:** Resolved from `os.getenv()` then `st.secrets` (backed by `.streamlit/secrets.toml`). No secrets manager; rotation is manual. Risk of secrets in file and no root `.gitignore` for secrets.

**Performance**

- **Sync only:** All I/O is synchronous (psycopg2, file writes). No async/await.
- **Blocking:** Board load runs reconciliation + backfill + N+1 queries (1 + 1 + 3×N for tasks/risks/notes) in the request. Import runs full pipeline in the request. Both can block for a long time and time out.

**Infrastructure**

- **Terraform:** None. No `.tf` files.
- **Environments:** No dev/staging/prod split in config or code; single `DATABASE_URL` (and optional auth) for all use.

---

## SUCCESS CRITERIA (WHAT MUST BE TRUE FOR PRODUCTION-READY)

| Criterion | Current state |
|-----------|----------------|
| No blocking AI calls in request cycle | **N/A** — no AI calls. When/if AI is wired, it must be offloaded (e.g. queue + worker) so the request cycle never blocks on LLM. |
| Queue + worker implemented | **Missing.** Import and midnight automation run in-process; no SQS (or equivalent) or worker service. |
| Caching layer active | **Missing.** No Redis. Only per-process Streamlit cache. |
| API Gateway in place | **Missing.** No API layer; no gateway/ALB in front of a backend API. |
| Secrets managed securely at runtime | **Missing.** Secrets from env or file (`secrets.toml`); not from a secret manager; rotation not automated. |
| Full environment separation (dev/staging/prod) | **Missing.** Single config; no env-specific resources or config. |
| Observability: logs + tracing + alerts | **Missing.** Plain logging, no structured/JSON logs, no trace IDs, no tracing, no alerting. |
| CI/CD fully automated | **Missing.** No GitHub Actions or other pipeline in repo. |

---

## WHAT PREVENTS PRODUCTION-READINESS

1. **Architecture mismatch:** App is a Streamlit + Postgres monolith. Target (React, FastAPI, Supabase, AWS, Terraform) is not implemented.
2. **No queue/worker:** Heavy work (import, midnight automation) blocks or runs in a single script; no decoupling, retries, or backpressure.
3. **No shared cache or rate limiting:** No Redis; scaling and abuse protection are limited.
4. **No API entry layer:** No gateway/ALB for an API; no central TLS/rate limit/auth at the edge.
5. **Auth and secrets:** Weak auth (optional password, no Supabase/JWT); secrets in env/file, not runtime-injected from a secret manager.
6. **No RLS:** Single DB role; no row-level isolation if multiple tenants or users are introduced.
7. **No observability:** Can’t correlate requests, trace latency, or alert on failures.
8. **No CI/CD:** Deploys and quality gates are not automated.
9. **No environment isolation:** One config and DB pattern; high risk for production vs dev/staging.


# TARGET SYSTEM BLUEPRINT (POST-REFACTOR)

## 1. SYSTEM GOAL

**Core problem**

- Operational sync and execution layer for apartment turnover: ingest PMS report data, keep turnover state aligned with reports, and support daily workflows (board, readiness, SLA, repairs). It is not the PMS, accounting, or leasing system.

**Key workflows**

1. **Ingest**  
   User uploads a PMS report file (CSV/xlsx) for a property and report type → API accepts upload, enqueues a job → worker validates schema and content, applies report rules, writes batch + rows + turnover/task/audit updates. API returns job id; client polls or receives webhook for completion. No long-running work in the request path.

2. **Board**  
   User selects property (and optional filters) → frontend calls API with JWT → API reads from Redis when valid cache exists, else queries Supabase (with RLS) → returns board payload (turnovers, units, tasks, readiness, SLA, priority). All reads are fast; no reconciliation or backfill in the request. Reconciliation/backfill runs in workers triggered by imports or a scheduled job.

3. **Unit/turnover detail and edits**  
   User opens a turnover → API returns detail (turnover, unit, tasks, notes). User submits an edit → API validates, optionally enqueues a small write job or performs a quick DB write, returns success. Heavy or multi-step updates go through the queue.

4. **Scheduled automation**  
   Scheduler (cron or EventBridge) enqueues a “midnight automation” job per property (or one job with a list). Worker runs transitions (e.g. On Notice → Vacant Not Ready by date) and creates turnovers from snapshots. No cron process calling the DB directly; all via queue + worker.

5. **Admin**  
   Property CRUD, phase scope, feature toggles (e.g. DB writes), unit/task-template management. All via API with JWT; writes are validated and audited.

6. **AI assistant**  
   User sends a message in the AI UI → frontend calls API with prompt and session id → API enqueues an “AI completion” job and returns job id → worker calls LLM (e.g. OpenAI) with prompt + context (e.g. board summary), writes reply to DB or cache, and optionally notifies client (polling or push). Frontend polls for result or subscribes to updates. No LLM call in the API process.

**Where and how AI is used**

- **Where:** Conversational assistant (e.g. “How many units are vacant?”, “Morning briefing”). Used only in the dedicated AI flow.
- **How:** User prompt → API creates job → worker pulls job, fetches allowed context (e.g. read-only board/metrics), calls LLM API, stores/serves response. All AI calls are async (queue + worker); API never blocks on AI. Rate limits and cost controls apply to the worker’s LLM usage.

---

## 2. USERS

**Roles**

- **Operator:** Daily use: board, unit detail, morning workflow, flag bridge, risk radar, possibly light imports.
- **Admin:** Property and phase setup, DB-writes toggle, unit/task-template management, repair/diagnostics.
- **System:** Scheduler and workers; no human UI; identity via IAM or app credentials, not Supabase JWT.

**How they interact**

- **Web app:** Primary. React (Vite, TypeScript, Tailwind) on S3 + CloudFront (or Amplify). Users sign in, then all data and actions go through the API.
- **API:** All app traffic and any future integrations go through API Gateway → FastAPI. No direct Supabase or backend URL exposure to the browser. Optional: separate API keys for programmatic access (machine-to-machine), with rate limits and scopes.

**Authentication (Supabase Auth + JWT)**

- **Sign-in:** User enters credentials (or uses OAuth if configured) in the React app. Frontend calls Supabase Auth (e.g. `signInWithPassword` or OAuth). Supabase returns a JWT (access + refresh).
- **Requests:** Frontend sends `Authorization: Bearer <access_token>` on every API request. API Gateway or FastAPI validates the JWT (signature, issuer, expiry) and optionally checks audience. Invalid or missing token → 401.
- **Refresh:** Before expiry, frontend uses the refresh token to get a new access token; no user re-login for normal sessions.
- **RLS:** Supabase Postgres uses `auth.uid()` (and optionally role claims) in RLS policies so each user only sees rows they are allowed to see. Backend uses the same JWT to connect as that user (or a service role for system jobs, with strict scope).

---

## 3. INPUTS

**User inputs (web app)**

- **Auth:** Email + password (and/or OAuth). Validated by Supabase Auth.
- **Property selection:** Property id (from list returned by API). API validates that the authenticated user can access that property (or RLS does).
- **Import:** Report type (enum: MOVE_OUTS, PENDING_MOVE_INS, AVAILABLE_UNITS, PENDING_FAS), file (CSV or xlsx). Max size enforced at API (e.g. 10 MB). Content-type and extension validated.
- **Board filters:** Property id, optional phase ids, priority, readiness, assignee, flag category. All validated as allowed enums or ids for that property.
- **Unit/turnover edits:** Turnover id, task id (if applicable), payload (e.g. task status, dates, assignee). API validates entity exists, user has access, and payload matches schema.
- **Admin:** Property name (non-empty, length cap), phase scope (list of phase ids), toggle values (e.g. enable_db_writes boolean). All validated at API.
- **AI:** Session id (or null for new), message text. Length and rate limits enforced at API; content may be sanitized.

**API request structures**

- **REST:** JSON bodies for POST/PATCH. Query params for filters and pagination. Headers: `Authorization: Bearer <jwt>`, `Content-Type: application/json`.
- **File upload:** Multipart form: `file` + optional `report_type`, `property_id`. Or presigned S3 upload then API with `bucket`, `key`, `report_type`, `property_id`.
- **Validation:** Every request is validated (Pydantic or equivalent): types, required fields, enums, ranges, size limits. Invalid → 400 with clear errors. No business logic on invalid payloads.

**External data sources**

- **PMS reports:** User-supplied files only. No automatic pull from external PMS APIs in this blueprint; if added later, they would be ingested via worker jobs.
- **Supabase:** Source of truth for DB (Postgres), Auth (JWTs), and optional Storage (e.g. imported file blobs). All access via Supabase APIs or Postgres with RLS.
- **AI provider:** Worker calls OpenAI (or configured provider) with prompts and optional context. No direct call from frontend or API process.

---

## 4. OUTPUTS

**To users (UI)**

- **Auth:** Redirect or token payload after sign-in; session state (user id, email, optional role) for the SPA.
- **Board / Flag Bridge / Risk Radar / Morning workflow:** JSON from API (turnovers, units, tasks, readiness, SLA, priorities, metrics). React renders tables, filters, and links. Pagination or cursor when needed.
- **Unit/turnover detail:** JSON (turnover, unit, tasks, notes, audit). Edits return updated resource or 202 + job id.
- **Import:** 202 + job id; then polling or webhook returns final status (SUCCESS / FAILED), batch id, counts, and diagnostics.
- **AI:** 202 + job id; then polling or push returns assistant message(s). Errors returned as structured messages.

**Stored**

- **Supabase Postgres:** Properties, phases, buildings, units, turnovers, tasks, notes, risk flags, SLA events, audit log, import batches/rows, snapshots, phase scope, system settings. All with RLS. Indexes on foreign keys and common filters.
- **Supabase Storage (optional):** Original import files (keyed by batch id / property) for audit and re-runs.
- **Redis:** Cache entries for board payloads, metrics, and possibly session or rate-limit data. TTLs and invalidation on writes (e.g. after import or edit jobs complete).

**Processed async (queue → worker)**

- **Import job:** Parse file, validate rows, apply report rules, write batch + rows + turnover/task/audit updates. On success: invalidate cache for that property. On failure: mark batch failed, store diagnostics.
- **Midnight automation job:** Per property (or batch): transition On Notice → Vacant Not Ready by date; create turnovers from snapshots; ensure tasks. No response to user; idempotent.
- **AI completion job:** Load context (e.g. board summary), call LLM, store reply, optionally invalidate or update AI session cache. Result consumed by polling or push.
- **Heavy or multi-step writes (optional):** Large bulk updates or complex state changes can be implemented as jobs; API returns job id and worker performs the work.

**External calls**

- **From API process:** Supabase (Postgres + Auth) for reads and quick writes; Redis for cache and rate limiting. No LLM calls. Optional: call to queue service (e.g. SQS send) to enqueue jobs.
- **From workers:** Supabase (Postgres, optionally Storage), SQS (receive/delete), Redis (cache invalidation, rate limit), and LLM provider (AI worker only). Workers do not serve user traffic.

---

## 5. INTEGRATIONS (FINAL SYSTEM)

**Frontend**

- React 18+, Vite, TypeScript (strict), Tailwind.
- Hosted on AWS: static assets on S3, delivery via CloudFront (or Amplify). HTTPS only. No backend secrets in the bundle; auth via Supabase client and JWTs.

**Backend**

- FastAPI, async-first. Dockerized. Serves only behind API Gateway (or ALB). No long-running or blocking AI/import logic in request handlers; those enqueue jobs.

**Infrastructure**

- **Entry:** API Gateway (REST or HTTP API) in front of the FastAPI service. Handles TLS, routing, and optionally request validation and rate limiting at the edge.
- **Compute:** App Runner (short term) for the API service; migration path to ECS (Fargate or EC2) for scaling. Worker(s) run as separate container(s), consuming from SQS.

**Data**

- **Supabase:** Postgres (primary DB, RLS on), Auth (issue/validate JWTs), optional Storage for files. Connection from API and workers via connection pool; credentials from secrets manager.

**Async**

- **SQS:** Queues for import jobs, midnight automation, AI completion, and any other background work. Dead-letter queues and retry policies defined. Workers poll (or long-poll) and process one message at a time (or bounded concurrency).
- **Worker service:** Separate container image(s), same or separate ECS service / App Runner. Pulls from SQS, calls Supabase, Redis, and (for AI queue) LLM API. No user-facing HTTP.

**Caching**

- **Redis:** Elasticache (or equivalent). Used for: board/metrics cache (keyed by property + scope), rate limiting counters, optional session or AI context cache. TTLs and explicit invalidation on relevant writes.

**Observability**

- **CloudWatch:** Logs from API and workers (structured JSON); metrics (request count, latency, error rate, queue depth, worker duration).
- **Tracing:** X-Ray or OpenTelemetry. Every request and job has a trace id; propagated to Supabase and Redis calls. Sampling configurable.
- **Alerts:** On failure rate, latency percentiles, queue backlog, worker errors, and cost anomalies. Channels (e.g. SNS → email/Slack) defined in Terraform or config.

**CI/CD**

- **GitHub Actions:** On push/PR: lint, typecheck, unit and integration tests. On merge to main (or release branch): build Docker images, push to ECR, deploy to dev then staging then prod (or as defined). No manual deploy steps for standard path. Secrets and env differ per environment.

**Secrets**

- **AWS Secrets Manager:** DB URL, Supabase service key, Redis URL, LLM API key, etc. Injected at runtime into API and worker containers (env or sidecar). Not in code, not in images, not in Terraform state as plaintext. Rotation supported by Secrets Manager; app uses latest.

---

## 6. CONSTRAINTS

- **Frontend:** Strict TypeScript; no `any` escape hatches for core flows. All API payloads typed (generated or shared types).
- **Backend:** FastAPI async-first; no blocking calls in request path. DB and Redis via async drivers or run in thread pool with clear bounds.
- **API layer:** No long-running work. Imports, AI, and heavy automation are enqueued; handlers return quickly (e.g. 202 + job id).
- **AI:** All LLM calls in workers; API never calls the LLM.
- **Auth:** JWT required on every API request (except health); validated at gateway or FastAPI.
- **Data:** RLS enabled and enforced on Supabase Postgres for tenant/user isolation.
- **Infrastructure:** Fully defined in Terraform (API Gateway, App Runner/ECS, SQS, Redis, Secrets Manager, CloudWatch, etc.). No manual console-only resources for core path.
- **Network:** HTTPS only; TLS termination at CloudFront/API Gateway. CORS restricted to the frontend origin(s) and API domain(s).
- **Rate limiting:** At API Gateway (or equivalent) and/or in FastAPI using Redis counters; per-user or per-IP limits and burst limits defined.

---

## 7. SUCCESS CRITERIA (NON-NEGOTIABLE)

The system is production-ready only when:

- **API never blocks on AI or long tasks:** All such work is queued and processed by workers; API responds with 202 + job id or equivalent.
- **Queue + worker operational:** SQS and worker(s) deployed; import, midnight automation, and AI jobs are consumed and completed (or DLQ with alerts).
- **Redis in use:** Expensive or repeated reads (e.g. board, metrics) are cached in Redis with invalidation on writes; cache hit path is the norm for read-heavy screens.
- **API Gateway in front:** All production traffic to the API goes through API Gateway (or ALB) with TLS and routing; no direct public access to backend.
- **Secrets not in code or images:** All secrets come from Secrets Manager (or equivalent) at runtime.
- **Structured, searchable logs:** JSON logs with trace id, timestamp, level, message; queryable in CloudWatch (or equivalent).
- **Tracing:** Request and job traces with spans for DB, Redis, and external calls; usable for debugging latency and errors.
- **Alerts:** Configured for failures, latency SLOs, and cost spikes; on-call or runbook defined.
- **Environment isolation:** Dev, staging, prod each have separate accounts or namespaces, DBs, queues, and Redis; no shared prod credentials in non-prod.
- **CI/CD:** Push-to-deploy pipeline; no manual steps for deploy and rollback.
- **Independent worker scaling:** Worker count (or queue concurrency) can be increased without changing API capacity, and vice versa.

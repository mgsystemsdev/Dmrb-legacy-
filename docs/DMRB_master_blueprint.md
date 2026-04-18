# DMRB SYSTEM BLUEPRINT

**Digital Make Ready Board**

Production-Readiness Assessment, Gap Analysis, Current System Definition, and Target Architecture

Billingsley Company | Make Ready Operations
March 2026

---

## Table of Contents

- [Part I: Context and Migration Rationale](#part-i-context-and-migration-rationale)
  - [1.1 Current State](#11-current-state)
  - [1.2 Why Migrate](#12-why-migrate)
  - [1.3 Scope of This Document](#13-scope-of-this-document)
- [Part II: Target System Blueprint](#part-ii-target-system-blueprint)
  - [2.1 System Goal](#21-system-goal)
  - [2.2 Users](#22-users)
  - [2.3 Inputs](#23-inputs)
  - [2.4 Outputs](#24-outputs)
  - [2.5 Integrations (Final System)](#25-integrations-final-system)
  - [2.6 Constraints](#26-constraints)
  - [2.7 Success Criteria (Non-Negotiable)](#27-success-criteria-non-negotiable)
- [Part III: Current System Definition (From Code)](#part-iii-current-system-definition-from-code)
  - [3.1 System Goal (Current)](#31-system-goal-current)
  - [3.2 Users (Current)](#32-users-current)
  - [3.3 Inputs (Current)](#33-inputs-current)
  - [3.4 Outputs (Current)](#34-outputs-current)
  - [3.5 Integrations (Current)](#35-integrations-current)
  - [3.6 Constraints (Inferred from Code)](#36-constraints-inferred-from-code)
  - [3.7 Success Criteria Status (Current)](#37-success-criteria-status-current)
  - [3.8 What Prevents Production-Readiness](#38-what-prevents-production-readiness)
- [Part IV: Production-Readiness Gap Analysis](#part-iv-production-readiness-gap-analysis)
  - [4.1 Architecture Gaps](#41-architecture-gaps)
  - [4.2 Backend (FastAPI) Gaps](#42-backend-fastapi-gaps)
  - [4.3 Frontend Gaps](#43-frontend-gaps)
  - [4.4 Database and Auth (Supabase) Gaps](#44-database-and-auth-supabase-gaps)
  - [4.5 Infrastructure Gaps](#45-infrastructure-gaps)
  - [4.6 Security Risks](#46-security-risks)
  - [4.7 Performance and Scaling Risks](#47-performance-and-scaling-risks)
  - [4.8 Observability Gaps](#48-observability-gaps)
  - [4.9 Failure Points](#49-failure-points)
- [Part V: Prioritized Fix List](#part-v-prioritized-fix-list)
  - [5.1 P0 — Must Fix Before Production](#51-p0--must-fix-before-production)
  - [5.2 P1 — Should Fix Soon](#52-p1--should-fix-soon)
  - [5.3 P2 — Improvements](#53-p2--improvements)
- [Part VI: Critical System Validation (Mandatory)](#part-vi-critical-system-validation-mandatory)
- [Summary](#summary)

---

# Part I: Context and Migration Rationale

## 1.1 Current State

The DMRB currently operates as a single Streamlit and PostgreSQL application. One process serves the UI and performs all work (imports, board load, reconciliation, backfill) within the request cycle. The database uses a single global connection. Authentication is optional, based on an in-memory username and password. Configuration and secrets come from environment variables or a local file.

There is no React or FastAPI layer, no queue, no Redis, no API layer, no Terraform, no CI/CD pipeline, and no observability. The AI screen is a stub with no LLM integration. Long-running work blocks the UI. There is no worker or cache.

## 1.2 Why Migrate

The migration is required to reach a production-ready system: safe secrets management, real authentication, non-blocking requests, scalable reads (cache) and writes (queue plus workers), a proper API and frontend, infrastructure as code, and full observability. The current stack cannot support these requirements without a structural change.

## 1.3 Scope of This Document

From this point forward, this document describes only the target system — the one being built step by step with checkpoints. No further reference to the old implementation is included except within the Gap Analysis and Current System Definition sections, which exist to document the baseline for migration planning.

---

# Part II: Target System Blueprint

## 2.1 System Goal

### 2.1.1 Core Job

Act as the operational sync and execution layer for apartment turnover: ingest PMS report data (files), keep turnover state aligned with those reports, and support daily workflows (board, readiness, SLA, repairs). It is not the PMS, accounting, or leasing system.

### 2.1.2 Main Workflows

- **Ingest:** Accept report uploads, enqueue jobs. Workers validate and apply rules, then update batches, rows, turnovers, tasks, and audit. API returns immediately with a job ID.
- **Board (and related views):** Serve read-optimized board data (turnovers, units, tasks, readiness, SLA, priority) from cache or DB, with filters. No heavy reconciliation in the request path; that runs in workers after imports or on schedule.
- **Detail and edits:** Serve unit and turnover detail; accept edits (validated at API); quick writes in API or small jobs; heavy or bulk updates via queue.
- **Scheduled automation:** Midnight-style automation (e.g. On Notice to Vacant Not Ready, create turnovers from snapshots) runs only as queue jobs consumed by workers.
- **Admin:** Property and phase setup, toggles (e.g. DB writes), unit and task-template management, all via API.
- **AI assistant:** User sends a message. API enqueues an AI job. Worker calls LLM with allowed context. Result stored and served asynchronously. No LLM calls in the API process.

### 2.1.3 Where and How AI Is Used

The AI assistant serves as a conversational interface for operational queries (e.g. "How many units are vacant?", "Morning briefing"). It is used only in the dedicated AI flow.

User prompt flows to the API, which creates a job. The worker pulls the job, fetches allowed context (e.g. read-only board and metrics), calls the LLM API, and stores or serves the response. All AI calls are asynchronous (queue plus worker). The API never blocks on AI. Rate limits and cost controls apply to the worker's LLM usage.

---

## 2.2 Users

### 2.2.1 Roles

- **Operator:** Uses the web app daily: board, unit detail, morning workflow, flag bridge, risk radar, light imports. Authenticates via Supabase Auth; all actions through the API with JWT.
- **Admin:** Uses the same web app with access to admin surfaces: property and phase config, DB-writes toggle, unit and task-template management, repair and diagnostics. Same auth and API.
- **System:** Scheduler and workers; no UI. Triggered by queues (and optionally cron or EventBridge). Identity via IAM or app credentials; no end-user JWT.

### 2.2.2 Interface

Primary interface is the React (Vite, TypeScript, Tailwind) SPA on S3 plus CloudFront. All data and actions go through the API (FastAPI behind API Gateway). Optional future: machine-to-machine API with keys and scopes.

### 2.2.3 Authentication (Supabase Auth and JWT)

- **Sign-in:** User enters credentials (or uses OAuth if configured) in the React app. Frontend calls Supabase Auth (e.g. signInWithPassword or OAuth). Supabase returns a JWT (access plus refresh).
- **Requests:** Frontend sends Authorization: Bearer <access_token> on every API request. API Gateway or FastAPI validates the JWT (signature, issuer, expiry) and optionally checks audience. Invalid or missing token returns 401.
- **Refresh:** Before expiry, frontend uses the refresh token to get a new access token; no user re-login for normal sessions.
- **RLS:** Supabase Postgres uses auth.uid() (and optionally role claims) in RLS policies so each user only sees rows they are allowed to see. Backend uses the same JWT to connect as that user (or a service role for system jobs, with strict scope).

---

## 2.3 Inputs

### 2.3.1 User Inputs (Web App)

- **Auth:** Email plus password (and/or OAuth) routed to Supabase Auth; no business logic in the API.
- **Property selection:** Property ID (from API-supplied list); validated for access (API or RLS).
- **Import:** Report type (enum: MOVE_OUTS, PENDING_MOVE_INS, AVAILABLE_UNITS, PENDING_FAS), file (CSV or xlsx), max size (e.g. 10 MB). Multipart or presigned upload plus metadata.
- **Board and filters:** Property ID, optional phase IDs, priority, readiness, assignee, flag category. Enums and IDs validated at API.
- **Unit and turnover edits:** Turnover and task IDs plus payload (e.g. status, dates, assignee). Validated against schema and access.
- **Admin:** Property name, phase scope (list of phase IDs), toggles (e.g. boolean). Validated at API.
- **AI:** Session ID (or null), message text. Length and rate limits enforced.

### 2.3.2 API Request Structures

- **REST:** JSON bodies for POST/PATCH. Query params for filters and pagination. Headers: Authorization: Bearer <jwt>, Content-Type: application/json.
- **File upload:** Multipart form: file plus optional report_type and property_id. Or presigned S3 upload then API with bucket, key, report_type, property_id.
- **Validation:** Every request is validated (Pydantic or equivalent): types, required fields, enums, ranges, size limits. Invalid returns 400 with clear errors. No business logic on invalid payloads.

### 2.3.3 External Data Sources

- **PMS reports:** User-supplied files only. No automatic pull from external PMS APIs in this blueprint; if added later, they would be ingested via worker jobs.
- **Supabase:** Source of truth for DB (Postgres), Auth (JWTs), and optional Storage (e.g. imported file blobs). All access via Supabase APIs or Postgres with RLS.
- **AI provider:** Worker calls OpenAI (or configured provider) with prompts and optional context. No direct call from frontend or API process.

---

## 2.4 Outputs

### 2.4.1 To Users (UI)

- **Auth:** Redirect or token payload after sign-in; session state (user ID, email, optional role) for the SPA.
- **Board / Flag Bridge / Risk Radar / Morning Workflow:** JSON from API (turnovers, units, tasks, readiness, SLA, priorities, metrics). React renders tables, filters, and links. Pagination or cursor when needed.
- **Unit and turnover detail:** JSON (turnover, unit, tasks, notes, audit). Edits return updated resource or 202 plus job ID.
- **Import:** 202 plus job ID; then polling or webhook returns final status (SUCCESS / FAILED), batch ID, counts, and diagnostics.
- **AI:** 202 plus job ID; then polling or push returns assistant message(s). Errors returned as structured messages.

### 2.4.2 Stored

- **Supabase Postgres:** Properties, phases, buildings, units, turnovers, tasks, notes, risk flags, SLA events, audit log, import batches/rows, snapshots, phase scope, system settings. All with RLS. Indexes on foreign keys and common filters.
- **Supabase Storage (optional):** Original import files (keyed by batch ID / property) for audit and re-runs.
- **Redis:** Cache entries for board payloads, metrics, and possibly session or rate-limit data. TTLs and invalidation on writes (e.g. after import or edit jobs complete).

### 2.4.3 Processed Async (Queue to Worker)

- **Import job:** Parse file, validate rows, apply report rules, write batch plus rows plus turnover/task/audit updates. On success: invalidate cache for that property. On failure: mark batch failed, store diagnostics.
- **Midnight automation job:** Per property (or batch): transition On Notice to Vacant Not Ready by date; create turnovers from snapshots; ensure tasks. No response to user; idempotent.
- **AI completion job:** Load context (e.g. board summary), call LLM, store reply, optionally invalidate or update AI session cache. Result consumed by polling or push.
- **Heavy or multi-step writes (optional):** Large bulk updates or complex state changes can be implemented as jobs; API returns job ID and worker performs the work.

### 2.4.4 External Calls

- **From API process:** Supabase (Postgres plus Auth) for reads and quick writes; Redis for cache and rate limiting. No LLM calls. Optional: call to queue service (e.g. SQS send) to enqueue jobs.
- **From workers:** Supabase (Postgres, optionally Storage), SQS (receive/delete), Redis (cache invalidation, rate limit), and LLM provider (AI worker only). Workers do not serve user traffic.

---

## 2.5 Integrations (Final System)

| Component | Specification |
|-----------|---------------|
| **Frontend** | React 18+, Vite, TypeScript (strict), Tailwind. Hosted on AWS: static assets on S3, delivery via CloudFront (or Amplify). HTTPS only. No backend secrets in the bundle; auth via Supabase client and JWTs. |
| **Backend** | FastAPI, async-first. Dockerized. Serves only behind API Gateway (or ALB). No long-running or blocking AI/import logic in request handlers; those enqueue jobs. |
| **Entry** | API Gateway (REST or HTTP API) in front of the FastAPI service. Handles TLS, routing, and optionally request validation and rate limiting at the edge. |
| **Compute** | App Runner (short term) for the API service; migration path to ECS (Fargate or EC2) for scaling. Worker(s) run as separate container(s), consuming from SQS. |
| **Data** | Supabase: Postgres (primary DB, RLS on), Auth (issue/validate JWTs), optional Storage for files. Connection from API and workers via connection pool; credentials from secrets manager. |
| **Async** | SQS: Queues for import jobs, midnight automation, AI completion, and any other background work. Dead-letter queues and retry policies defined. Workers poll (or long-poll) and process one message at a time (or bounded concurrency). |
| **Worker** | Separate container image(s), same or separate ECS service / App Runner. Pulls from SQS, calls Supabase, Redis, and (for AI queue) LLM API. No user-facing HTTP. |
| **Caching** | Redis (Elasticache or equivalent). Used for: board/metrics cache (keyed by property plus scope), rate limiting counters, optional session or AI context cache. TTLs and explicit invalidation on relevant writes. |
| **Observability** | CloudWatch: logs from API and workers (structured JSON); metrics (request count, latency, error rate, queue depth, worker duration). X-Ray or OpenTelemetry for tracing. Alerts on failures, latency, queue backlog, and cost anomalies. |
| **CI/CD** | GitHub Actions: On push/PR: lint, typecheck, unit and integration tests. On merge to main: build Docker images, push to ECR, deploy to dev then staging then prod. No manual deploy steps. |
| **Secrets** | AWS Secrets Manager: DB URL, Supabase service key, Redis URL, LLM API key, etc. Injected at runtime into API and worker containers. Not in code, images, or Terraform state as plaintext. Rotation supported. |

---

## 2.6 Constraints

- **Frontend:** Strict TypeScript; no 'any' escape hatches for core flows. All API payloads typed (generated or shared types).
- **Backend:** FastAPI async-first; no blocking calls in request path. DB and Redis via async drivers or run in thread pool with clear bounds.
- **API layer:** No long-running work. Imports, AI, and heavy automation are enqueued; handlers return quickly (e.g. 202 plus job ID).
- **AI:** All LLM calls in workers; API never calls the LLM.
- **Auth:** JWT required on every API request (except health); validated at gateway or FastAPI.
- **Data:** RLS enabled and enforced on Supabase Postgres for tenant and user isolation.
- **Infrastructure:** Fully defined in Terraform (API Gateway, App Runner/ECS, SQS, Redis, Secrets Manager, CloudWatch, etc.). No manual console-only resources for core path.
- **Network:** HTTPS only; TLS termination at CloudFront or API Gateway. CORS restricted to the frontend origin(s) and API domain(s).
- **Rate limiting:** At API Gateway (or equivalent) and/or in FastAPI using Redis counters; per-user or per-IP limits and burst limits defined.

---

## 2.7 Success Criteria (Non-Negotiable)

The system is production-ready only when all of the following are true:

- API never blocks on AI or long tasks — all such work is queued and processed by workers; API responds with 202 plus job ID or equivalent.
- Queue plus worker operational — SQS and worker(s) deployed; import, midnight automation, and AI jobs are consumed and completed (or DLQ with alerts).
- Redis in use — expensive or repeated reads (e.g. board, metrics) are cached in Redis with invalidation on writes; cache hit path is the norm for read-heavy screens.
- API Gateway in front — all production traffic to the API goes through API Gateway (or ALB) with TLS and routing; no direct public access to backend.
- Secrets not in code or images — all secrets come from Secrets Manager (or equivalent) at runtime.
- Structured, searchable logs — JSON logs with trace ID, timestamp, level, message; queryable in CloudWatch (or equivalent).
- Tracing — request and job traces with spans for DB, Redis, and external calls; usable for debugging latency and errors.
- Alerts — configured for failures, latency SLOs, and cost spikes; on-call or runbook defined.
- Environment isolation — dev, staging, prod each have separate accounts or namespaces, DBs, queues, and Redis; no shared prod credentials in non-prod.
- CI/CD — push-to-deploy pipeline; no manual steps for deploy and rollback.
- Independent worker scaling — worker count (or queue concurrency) can be increased without changing API capacity, and vice versa.

---

# Part III: Current System Definition (From Code)

## 3.1 System Goal (Current)

### 3.1.1 What It Does End-to-End

**Problem:** Keeps apartment turnover state in sync with PMS reports and supports day-to-day operations (board, readiness, SLA, repairs). It is not the PMS, accounting, or leasing system.

**Current workflows:**

1. **Ingest:** User uploads PMS CSV (or xlsx) for one of four report types. System performs checksum, schema check, parse, per-row validation and conflict handling. Batch written to DB; turnovers, tasks, and audit updated per report rules.
2. **Board:** User picks property. App loads open turnovers, units, tasks, risks, notes. Reconciles from latest Available Units, ensures on-notice turnovers, backfills tasks. Computes lifecycle, readiness, SLA, agreements, priority. Renders filterable board (and Flag Bridge, Risk Radar, Morning Workflow from same data).
3. **Unit/turnover detail:** User selects a turnover. Detail view with tasks, notes, readiness; inline edits (task status, dates, etc.) when DB writes are enabled.
4. **Admin:** Property CRUD, phase scope, DB-writes toggle (persisted in system_settings), unit master import, task template management.
5. **Import automation (out-of-app):** Cron runs scripts/run_midnight_automation.py. For each property, transitions On Notice to Vacant Not Ready by available_date, creates turnovers from unit_on_notice_snapshot where available_date is today or earlier. No queue, runs in one process.
6. **Repair/diagnostics:** Import Reports and Repair Reports screens show non-OK import rows, conflicts, missing move-outs, etc. User can fix data or re-import.
7. **Export/Work order validator/Operations schedule:** UI surfaces exist; export generation and full behavior are not implemented in the reviewed code paths.

### 3.1.2 AI (Current State)

- **Where:** Only the DMRB AI Agent screen (ui/screens/ai_agent.py).
- **Reality:** Docstring states: "Placeholder data only — no LLM API wired yet." Replies are hardcoded. No OpenAI, Anthropic, or other LLM calls in the codebase.
- **Conclusion:** AI is not used; the screen is a stub.

---

## 3.2 Users (Current)

**Who:** One effective role: anyone who can open the app. No role or permission checks in code beyond "can I see the app" (auth gate).

**How they interact:** Web app only. Streamlit server; users use the browser. No REST/API for external clients. CLI only for run_midnight_automation.py (and similar scripts).

**Authentication:** Implemented in ui/auth.py: If APP_USERNAME or APP_PASSWORD is set (env or st.secrets), a login form is displayed; success sets st.session_state.authenticated to True. If both are unset, require_auth() sets authenticated to True and returns with no login. No Supabase Auth, no JWT, no OAuth, no session expiry. Auth is in-memory session state only.

---

## 3.3 Inputs (Current)

| Source | Format | Validation |
|--------|--------|------------|
| **Login** | Form: username, password (plain text) | Compared to APP_USERNAME/APP_PASSWORD; no rate limit, no lockout. |
| **Property selection** | Sidebar selectbox to st.session_state.property_id | From property_service.get_all_properties(); no server-side check that user may access that property. |
| **Import files** | CSV or xlsx upload; in-memory bytes then temp file for orchestrator | File: validate_import_file (file_validator); schema: validate_import_schema (required columns per report type, skiprows). No max file size; no row limit. |
| **Report type** | Fixed set: MOVE_OUTS, PENDING_MOVE_INS, AVAILABLE_UNITS, PENDING_FAS | Orchestrator routing; unknown type returns No handler and batch failed. |
| **Board/Flag filters** | Session state: priority, phase, readiness, assignee, flag category | From UI; filter applied in Python on already-loaded board list. |
| **Unit/turnover edits** | Forms / data_editor: task status, dates, assignee, turnover dates, etc. | Service/DB layer; write_guard checks DB writes toggle when in Streamlit context. |
| **Admin** | New property name, phase scope selection, DB writes checkbox, unit/task template edits | Persisted via services; no schema validation beyond DB. |
| **Midnight script** | CLI: optional --date YYYY-MM-DD | Parsed as date; invalid format exits 1. |
| **Config** | Env vars and/or .streamlit/secrets.toml | get_setting(): env wins, then st.secrets. No validation of DATABASE_URL format or required keys. |

There are no API request payloads (no public API). No external event or webhook inputs in code.

---

## 3.4 Outputs (Current)

- **UI:** Streamlit pages (board, flag bridge, risk radar, morning workflow, unit detail, import/repair/export screens, admin, AI agent stub). Responses are server-rendered HTML/WebSocket (Streamlit); no separate JSON API for the app.
- **Stored data:** PostgreSQL via db/connection and repositories. Tables: property, phase, building, unit, turnover, task_template, task, note, risk_flag, sla_event, audit_log, import_batch, import_row, turnover_task_override, unit_movings, unit_on_notice_snapshot, phase_scope, system_settings, etc. Writes go through services; many paths call check_writes_enabled() (when in Streamlit).
- **External calls:** None. No outbound HTTP to AI providers, webhooks, or third-party APIs in the codebase.
- **Background jobs:** No queue or worker. The only background behavior is the cron-driven script run_midnight_automation.py, which runs in a single process and is not part of the web app. Import runs synchronously in the Streamlit request that handles the upload.

---

## 3.5 Integrations (Current)

**Present in code:**

- **PostgreSQL:** Single connection via DATABASE_URL and psycopg2; prepare_threshold=None. No Supabase client used for DB.
- **Supabase:** SUPABASE_URL and SUPABASE_KEY are read in config/settings.py and never used elsewhere. No Supabase Auth, Storage, or Realtime.

**Not present (required for target production):**

- **SQS (queue):** Not used. Import and midnight automation are synchronous/in-process.
- **Redis (cache):** Not used. Only Streamlit in-memory cache (st.cache_data TTL 30/60s).
- **API Gateway (or ALB):** No API layer in front of the app; Streamlit is the only entry.
- **AWS (App Runner, S3, CloudFront, etc.):** No AWS resources or SDK usage in the repo.
- **AI providers:** No integration; AI Agent is a stub.

---

## 3.6 Constraints (Inferred from Code)

### 3.6.1 Tech Stack (Actual)

- **Frontend:** Streamlit (Python). No React, no TypeScript, no Tailwind.
- **Backend:** No FastAPI. Application process is Streamlit plus services plus db/connection; no separate API server.
- **Data:** PostgreSQL via psycopg2 and DATABASE_URL. Supabase is only in config, not in use.
- **Deploy:** No Dockerfile, no Terraform, no AWS/App Runner config in repo.

### 3.6.2 Security

- **JWT:** None. Auth is session-state plus optional username/password.
- **RLS:** Not used. Schema has no ENABLE ROW LEVEL SECURITY or policies; one DB credential sees all data.
- **Secrets:** Resolved from os.getenv() then st.secrets (backed by .streamlit/secrets.toml). No secrets manager; rotation is manual. Risk of secrets in file and no root .gitignore for secrets.

### 3.6.3 Performance

- **Sync only:** All I/O is synchronous (psycopg2, file writes). No async/await.
- **Blocking:** Board load runs reconciliation plus backfill plus N+1 queries (1 + 1 + 3×N for tasks/risks/notes) in the request. Import runs full pipeline in the request. Both can block for a long time and time out.

### 3.6.4 Infrastructure

- **Terraform:** None. No .tf files.
- **Environments:** No dev/staging/prod split in config or code; single DATABASE_URL (and optional auth) for all use.

---

## 3.7 Success Criteria Status (Current)

| Criterion | Current State |
|-----------|---------------|
| No blocking AI calls in request cycle | **N/A** — no AI calls. When/if AI is wired, it must be offloaded. |
| Queue + worker implemented | **MISSING.** Import and midnight automation run in-process; no SQS or worker service. |
| Caching layer active | **MISSING.** No Redis. Only per-process Streamlit cache. |
| API Gateway in place | **MISSING.** No API layer; no gateway/ALB in front of a backend API. |
| Secrets managed securely at runtime | **MISSING.** Secrets from env or file (secrets.toml); not from a secret manager. |
| Full environment separation | **MISSING.** Single config; no env-specific resources or config. |
| Observability: logs + tracing + alerts | **MISSING.** Plain logging, no structured/JSON logs, no trace IDs, no alerting. |
| CI/CD fully automated | **MISSING.** No GitHub Actions or other pipeline in repo. |

---

## 3.8 What Prevents Production-Readiness

1. **Architecture mismatch:** App is a Streamlit plus Postgres monolith. Target (React, FastAPI, Supabase, AWS, Terraform) is not implemented.
2. **No queue/worker:** Heavy work (import, midnight automation) blocks or runs in a single script; no decoupling, retries, or backpressure.
3. **No shared cache or rate limiting:** No Redis; scaling and abuse protection are limited.
4. **No API entry layer:** No gateway/ALB for an API; no central TLS/rate limit/auth at the edge.
5. **Auth and secrets:** Weak auth (optional password, no Supabase/JWT); secrets in env/file, not runtime-injected from a secret manager.
6. **No RLS:** Single DB role; no row-level isolation if multiple tenants or users are introduced.
7. **No observability:** Cannot correlate requests, trace latency, or alert on failures.
8. **No CI/CD:** Deploys and quality gates are not automated.
9. **No environment isolation:** One config and DB pattern; high risk for production vs dev/staging.

---

# Part IV: Production-Readiness Gap Analysis

## 4.1 Architecture Gaps

| Component | Current | Target |
|-----------|---------|--------|
| **Frontend** | Streamlit (Python). No React, Vite, TypeScript, or Tailwind. | React (Vite + TypeScript strict + Tailwind) |
| **Backend** | No FastAPI. No HTTP API layer. Streamlit talks directly to DB. | FastAPI (Dockerized) |
| **Hosting** | No Amplify, S3, or CloudFront. No deploy config. | AWS (Amplify or S3 + CloudFront) |
| **API Entry** | No API Gateway or ALB. Streamlit is the only entry. | API Gateway or ALB |
| **Queue** | No SQS or any queue. Import/midnight run in-process. | SQS + worker |
| **Worker** | No background worker service. | Worker service (background processing) |
| **Caching** | No Redis. Streamlit in-memory only (st.cache_data). | Redis (caching + rate limiting) |
| **CI/CD** | No .github/workflows or pipeline. | CI/CD (GitHub Actions) |
| **Observability** | No structured JSON logs, no tracing, no alerting. | Observability (logs, tracing, alerts) |
| **IaC** | No .tf files. No Terraform. | Terraform (ALL AWS resources) |
| **Supabase** | Postgres only via psycopg2. SUPABASE_URL/KEY unused. No Auth or Storage. | Supabase (Postgres + Auth + Storage) |

---

## 4.2 Backend (FastAPI) Gaps

- **No FastAPI:** There is no FastAPI app. The backend is Streamlit plus services plus db/connection.
- **Blocking DB:** All DB access is synchronous (psycopg2, get_connection()). Every board load, import, and script blocks the process.
- **Single global connection:** db/connection.py uses one global _connection. No connection pool. Under concurrency, one connection is shared; risk of connection exhaustion, errors, or serialization of all DB work.
- **Validation:** No Pydantic or request validation (no API). Input validation is ad hoc in services.
- **Token verification:** No JWT or API tokens. Auth is session-only (st.session_state.authenticated) and optional APP_USERNAME/APP_PASSWORD. If both are unset, require_auth() bypasses login.
- **Security:** Write guard is enforced only in Streamlit context; in CLI/scripts (get_script_run_ctx() is None) writes are always allowed. Midnight script can write even when DB Writes is off in Admin. No CSRF/XSRF in app code. No rate limiting.

---

## 4.3 Frontend Gaps

- **Not a SPA:** Frontend is Streamlit; no React, no client-side routing, no TypeScript.
- **State:** State is st.session_state (in-memory, server-side). No persistence across restarts; no Supabase Auth state. Session can be lost on redeploy or server restart.
- **API handling:** No REST client. Data comes from service calls in the same process. Large imports run synchronously; user waits and can hit timeouts or browser disconnect.
- **Auth flow:** Login is username/password vs env/secrets only; no OAuth, no Supabase Auth, no MFA. If empty, auth is skipped. No token refresh, no session expiry.
- **Error handling:** Exceptions in import/board show generic st.error(str(exc)) or are swallowed (e.g. get_board() wraps reconciliation in try/except: pass). No global error boundary, no retry UX.

---

## 4.4 Database and Auth (Supabase) Gaps

- **RLS:** Schema has no ENABLE ROW LEVEL SECURITY and no CREATE POLICY. All access is with the same DB role; any user with DB credentials sees all rows.
- **Queries:** Repositories use parameterized queries (%s). No raw string concatenation of user input into SQL. **PASS** on SQL injection for current usage.
- **Indexes:** Indexes exist for main access patterns. No obvious missing index for the current query set.
- **Auth misuse:** Supabase Auth is not used. DB is accessed with a single credential (DATABASE_URL); no per-user or per-tenant DB identity.

---

## 4.5 Infrastructure Gaps

- **Terraform:** No Terraform. No .tf files. No AWS resources defined as code.
- **Environments:** No dev/staging/prod separation in code or config. Single DATABASE_URL and optional APP_USERNAME/APP_PASSWORD.
- **Deploy:** No Dockerfile, no App Runner, no ECS/EKS. No defined runtime or scaling.

---

## 4.6 Security Risks

- **Secrets:** config/settings.py reads from os.getenv() then st.secrets. .streamlit/secrets.toml contains DATABASE_URL. Root .gitignore was not found. If secrets not ignored, secrets.toml can be committed and leak DB URL and any future secrets.
- **Rate limiting:** None. No Redis or in-app throttle. A single client can hammer the Streamlit app and exhaust resources.
- **Auth:** Weak. Optional basic username/password; when unset, no login. No Supabase Auth, no JWT, no session expiry.
- **CORS:** No custom CORS in app code. If an API is added later without restricting origins, risk of open CORS.

---

## 4.7 Performance and Scaling Risks

- **No Redis:** No shared cache. Board/import data is only in Streamlit in-memory cache (per process). Multiple instances do not share cache; DB load and latency stay high under traffic.
- **No queue:** Heavy work (import, midnight automation) is not offloaded. Import runs in the Streamlit process; midnight runs in a script. Under load, long-running work will block and can time out.
- **Long-running requests:** Board load runs reconcile_open_turnovers_from_latest_available_units, ensure_on_notice_turnovers_for_property, and backfill_tasks_for_property then builds the board. Import runs the full pipeline in one request. Both can exceed browser/Streamlit timeouts.
- **N+1 in board:** get_board() does: 1 query for turnovers, 1 for units, then per turnover task_repository.get_by_turnover, risk_repository.get_open_by_turnover, note_repository.get_by_turnover. So 1 + 1 + 3×N queries. With hundreds of turnovers, this will be slow.

---

## 4.8 Observability Gaps

- **Logs:** Some services use logging.getLogger. Logs are not structured (JSON). No request/session/trace IDs. Correlating logs is hard.
- **Tracing:** No OpenTelemetry, no X-Ray. No distributed or request-level tracing.
- **Alerts:** No alerting config. Failures and degradation can go unnoticed.

---

## 4.9 Failure Points

- **Board load under load:** Many open turnovers lead to N+1 queries plus reconciliation/backfill. Single connection, blocking I/O. Result: slow responses, timeouts, or Streamlit/connection errors. Exceptions in reconciliation are swallowed (try/except: pass), so silent partial failures with no alert.
- **Import in UI:** Large file runs in-process. Can hit Streamlit/HTTP timeouts; user sees generic error. No retry, no job queue; duplicate or partial state possible if user retries.
- **Midnight script:** No queue, no retries. If script fails (DB, OOM, crash), run is lost until next cron. No dead-letter, no visibility.
- **DB connection:** Single global connection. If it drops (network, Supabase restart), all operations fail until restart. No reconnect or health check on reuse.
- **Secrets in file:** If secrets.toml is committed, anyone with repo access gets DB and app credentials; full DB and app compromise.

---

# Part V: Prioritized Fix List

## 5.1 P0 — Must Fix Before Production

1. **Secrets:** Ensure .streamlit/secrets.toml (and any file with secrets) is in .gitignore and never committed; use env or a secrets manager at runtime.
2. **Auth:** Require auth (no bypass when APP_USERNAME/APP_PASSWORD unset) or integrate Supabase Auth and enforce it on every sensitive path.
3. **DB connection:** Replace single global connection with a connection pool (e.g. psycopg2.pool) or Supabase-backed pool; add reconnect/health check so one bad connection does not take down the app.
4. **Long-running work:** Offload import and midnight automation to a queue (e.g. SQS) plus worker so Streamlit and cron do not block or timeout; add retries and clear failure visibility.
5. **RLS (if multi-tenant/Supabase):** Add RLS and policies before exposing Supabase or multi-tenant data; otherwise one credential exposes all data.

## 5.2 P1 — Should Fix Soon

6. **N+1 on board:** Batch-load tasks, risks, notes by turnover IDs (e.g. one query per entity type with WHERE turnover_id = ANY(%s)) instead of per-turnover calls in get_board().
7. **Observability:** Introduce structured (JSON) logs with request/session/correlation IDs; add tracing (e.g. OpenTelemetry/X-Ray) and at least one alert channel for errors and latency.
8. **Write guard:** Apply the same DB writes on/off behavior in CLI/scripts as in the UI (e.g. read system_settings or env) so midnight script respects the same guard.
9. **Error handling:** Replace broad except: pass in board load with logged, categorized handling and optional user-visible degraded state instead of silent wrong data.

## 5.3 P2 — Improvements

10. **API + gateway:** Introduce FastAPI (or similar) behind ALB/API Gateway for future mobile/API clients; add rate limiting (e.g. with Redis).
11. **Redis:** Add Redis for shared cache and rate limiting to reduce DB load and abuse.
12. **Align with target stack:** React (Vite + TS + Tailwind) frontend, FastAPI backend, Terraform, CI/CD, and Supabase Auth/Storage as per target architecture.

---

# Part VI: Critical System Validation (Mandatory)

This section provides a pass/fail assessment of each non-negotiable production-readiness criterion against the current codebase.

| Criterion | Status | Detail |
|-----------|--------|--------|
| **Async Processing** | ❌ FAIL | No SQS or equivalent. Import in ui/screens/import_console.py runs in-process. Midnight in scripts/run_midnight_automation.py runs in one process. Both can block and timeout; no worker, no retry. |
| **Caching** | ❌ FAIL | No Redis. Only Streamlit in-memory st.cache_data (TTL 30/60s). Repeated views hit DB every time after TTL; no shared cache. No Redis-based rate limiting. |
| **API Entry Layer** | ❌ FAIL | No API Gateway or ALB in front of a backend API. Streamlit is the only entry. No central TLS termination, rate limiting, or auth at the edge. |
| **Runtime Secrets** | ❌ FAIL | Secrets from os.getenv() or st.secrets (backed by secrets.toml on disk). Not injected by a secret manager at runtime. If committed or server is compromised, credentials are exposed. |
| **Observability Depth** | ❌ FAIL | Logs are plain text, not JSON; no tracing; no alerts. No request correlation, no latency breakdown, no automatic notification on failures. |
| **Environment Isolation** | ❌ FAIL | No separate dev/staging/prod config or resources. Single DB and app config. Deploys and experiments hit the same data. |
| **Scaling Limitations** | ❌ FAIL | No App Runner/ECS/EKS; no container or scaling config. Single-process Streamlit plus single DB connection will be bottleneck and single point of failure. |

---

# Summary

The codebase is a Streamlit plus PostgreSQL monolith with no React, no FastAPI, no Terraform, no queue, no Redis, no CI/CD, and no observability. It does not match the target architecture. To reach production readiness, address P0 first (secrets, auth, DB connection, offloading long-running work, and RLS if applicable), then P1 (N+1, observability, write guard, errors), then P2 (API, Redis, and full alignment with the target stack).
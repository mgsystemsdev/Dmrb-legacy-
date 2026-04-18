# Research → Architecture → Implementation Alignment Report

**Role:** Technical Director AI (senior technical reviewer)  
**Purpose:** Compare the research report, blueprint architecture, and actual codebase to evaluate how well the implementation supports the intended design.  
**Decision maker:** Human architect.

---

## Source of Truth

| Source | What it defines |
|--------|------------------|
| **Research Report** | `deep-research-report.md` — Production-grade Streamlit with Supabase PostgreSQL: execution model, layering, caching, DB access, deployment, security. Defines the *technical* and *operational* model the app should follow. |
| **Blueprint** | `spec/` (architecture, import_ops, ui, audits) and existing verification docs. The spec README references `blueprint.md` at repo root for “canonical system identity and invariants,” but **`blueprint.md` does not exist** in the repository. Blueprint content is inferred from `spec/architecture/*`, `ARCHITECTURE_VERIFICATION_REPORT.md`, and `STRUCTURAL_AUDIT.md`. |
| **Codebase** | The DMRB application: Streamlit UI, services, domain, db/repository, application workflows. |

**Important clarification:** The research report does **not** describe a learning model, puzzle runtime, or gameplay–learning loop. It describes how to build a **production Streamlit app** with Supabase (caching, layering, SQL, connection handling). The project is the **Digital Make Ready Board (DMRB)** — an operational app for apartment turnover and make-ready workflows, not an educational or puzzle game. This report therefore evaluates alignment of the **technical and architectural** recommendations from the research with the **spec** and the **implementation**.

---

## 1. Repository Summary (Current System)

Discovery summary of the codebase as implemented:

### 1.1 Core engine / application systems

- **Entrypoint:** `app.py` — thin (~94 lines): page config, CSS, session init, backend bootstrap, navigation, sidebar, router. No business logic; delegates to `ui/`.
- **Router:** `ui/router.py` — resolves current page and lazy-loads the corresponding `ui.screens.<name>` module so only the active screen is loaded.
- **Application layer:** `application/commands/`, `application/workflows/` — command dataclasses and write workflows that call services only (no direct repository or UI).

### 1.2 Domain and “runtime” behavior

- **Domain:** `domain/` — pure logic: lifecycle (effective move-out, phase), enrichment (board facts, SLA, risk), risk_engine, risk_radar, sla_engine, unit_identity. No DB or UI imports.
- **Services:** `services/` — orchestration and business workflows: turnover, task, board_query, import (orchestrator + report-specific modules), export, SLA, risk, note, chat, manual_availability, unit_master_import, property, unit, report_operations. All data access goes through `db/repository`.
- **Repository:** `db/repository/` — entity-scoped modules (units, turnovers, tasks, properties, risks, sla, notes, chat, imports, fas_tracker_notes) plus shared helpers. Used only by services (and bootstrap).

### 1.3 Adapter and infrastructure systems

- **DB:** `db/connection.py` — `get_connection()`, `ensure_database_ready()`; supports SQLite (test) and Postgres via `db/adapters/`. Postgres adapter uses `prepare_threshold=None` for Supabase transaction pooler compatibility.
- **Config:** `config/settings.py` — `get_settings()` (env + Streamlit secrets via `get_setting()`). Infrastructure depends on Streamlit here (noted as a violation in the architecture report).
- **Import validation:** `imports/validation/` — file and schema validation used by the import pipeline.

### 1.4 Content and data systems

- **Schema and migrations:** `db/schema.sql`, `db/migrations/*.sql` — canonical schema and ordered migrations; bootstrap applies them via `ensure_database_ready`.
- **Import contracts:** Spec’d in `spec/import_ops/`; implemented in `services/imports/` (move_outs, move_ins, available_units, pending_fas, dmrb, etc.).

### 1.5 UI systems

- **Screens:** `ui/screens/` — board, flag_bridge, risk_radar, turnover_detail, admin, ai_agent, unit_import, exports, report_operations. Each screen is a distinct module; router loads only the current one.
- **UI data:** `ui/data/backend.py` — backend availability and service refs; one-time bootstrap (DB ready + task backfill). `ui/data/cache.py` — `st.cache_data` wrappers for list/board/flag/detail, keyed by DB identity and TTL (5–10 s); `invalidate_ui_caches` and `invalidate_board_caches` for write paths.
- **UI state and helpers:** `ui/state/`, `ui/helpers/`, `ui/actions/db.py` — session state, constants, formatting, dates, dropdowns, DB write gate and cache clear on write.

### 1.6 Systems related to research goals

The research report’s “goals” are **technical**: correct Streamlit execution model, safe caching, clear layering, robust DB access, and deployment safety. The systems that directly support those are:

- **Caching:** `ui/data/cache.py` (data caching + invalidation).
- **Layering:** UI → application/workflows → services → repository; domain pure; infrastructure (db, config).
- **DB access:** `db/connection.py`, adapters, repository; parameterized queries in repository layer.
- **Bootstrap:** `ensure_database_ready` and backend bootstrap at startup (in `ui/data/backend.py`).

---

## 2. Research Model Summary

The research report defines a **technical and operational model** for Streamlit + Supabase apps, not a learning or gameplay model.

### 2.1 Core recommendations

- **Execution model:** Reruns run the script top to bottom; minimize cost via batching (e.g. `st.form`), caching, and (where applicable) fragments.
- **Layering:** Three layers — (1) **Presentation** (Streamlit pages/components, UI only), (2) **Application/Services** (stateless use cases: validate, fetch/mutate via repository, apply rules, return serializable results), (3) **Infrastructure** (DB, external APIs, secrets, logging).
- **Caching:** Use `st.cache_data` for data (TTL, clear on writes); use `st.cache_resource` for resources (e.g. DB connection). Do not mutate cached data; treat cache invalidation as a first-class API when writes occur.
- **DB:** Prefer Streamlit `st.connection("sql")` (SQLAlchemy-based, cached as resource); use parameterized queries; for Supabase **transaction** pooler, disable prepared statements (e.g. `prepare_threshold=None`). Sync access; connection pooling and health checks.
- **Config/secrets:** Env or Streamlit secrets; never commit secrets.
- **Deployment:** Session affinity if multiple replicas; SSL at reverse proxy; consistent `cookieSecret` across replicas.

### 2.2 Implied system requirements

- Single entrypoint or clear navigation; pages thin and delegating to services.
- Explicit “ensure DB ready” (schema + migrations) before any repository use.
- Cache invalidation paths after mutations so the UI does not show stale data indefinitely.
- No async for cached or connection-related code; sync DB with pooling.

---

## 3. Architecture Support (Blueprint vs Research)

The spec and verification docs describe an architecture that is **broadly aligned** with the research layers and concerns.

| Research idea | Blueprint (spec + verification) | Support |
|---------------|----------------------------------|--------|
| Presentation / Application / Infrastructure | UI → Application (workflows) → Services → Repository; Domain pure; Infrastructure (db, config) | Yes. Layers are named and dependency direction is specified. |
| Thin pages, logic in services | Router + thin screens; workflows and services hold logic | Yes. Screens delegate to services/cache; workflows call services only. |
| DB bootstrap before use | `spec/architecture/db_bootstrap_and_migrations_design.md`: `ensure_database_ready` at startup, schema + migrations | Yes. Design is implemented (see below). |
| Cache invalidation on writes | Not explicitly called out in the research-style “first-class API” form in spec | Partial. Implemented in code; not a first-class contract in the blueprint. |
| Connection as cached resource | Research recommends `st.connection` (cached resource) | Blueprint does not mandate `st.connection`; current design uses custom `db/connection` + adapters. |

**Gaps in the blueprint relative to research:**

- No explicit “cache invalidation contract” (when and how caches are cleared after which writes).
- No explicit requirement to cache the DB connection (research recommends resource caching; blueprint is silent).
- Referenced **`blueprint.md`** is missing, so “canonical system identity and invariants” are not in one place.

---

## 4. Implementation Alignment

### 4.1 Where the implementation matches the research and blueprint

| Area | Evidence |
|------|----------|
| **Thin entrypoint** | `app.py` is short; no business logic; imports backend, router, state, sidebar; runs bootstrap then navigation and current page. |
| **Layered structure** | UI uses services and cache only; application workflows call services; services use repository and domain; domain has no outward deps; repository and db/ are infrastructure. |
| **DB bootstrap at startup** | `ui/data/backend.py` calls `ensure_database_ready(db_path)` in `_bootstrap_once()` when backend loads; app entrypoint calls `bootstrap_backend_once()`. Schema and migrations are applied before normal reads/writes. |
| **Caching with TTL** | `ui/data/cache.py` uses `st.cache_data(ttl=5 or 10)` for list/board/flag/detail; cache key includes `db_cache_identity()` so different DBs don’t share data. |
| **Cache invalidation on writes** | After DB writes, `db_write` in `ui/actions/db.py` calls `st.cache_data.clear()`. Board save and admin import call `invalidate_ui_caches()` or `invalidate_board_caches()` so board-related caches are cleared. |
| **Supabase transaction pooler** | `db/adapters/postgres_adapter.py` uses `prepare_threshold=None` so prepared statements are disabled for Supabase transaction mode. |
| **Parameterized queries** | Repository uses parameterized SQL (e.g. `?` / `%s` via adapter); no string concatenation of user input into SQL. |
| **Secrets** | Config reads from env and `st.secrets`; no secrets committed in repo. |
| **Router lazy loading** | Only the active screen module is imported; other screens are not loaded until selected. |

### 4.2 Where the implementation matches the blueprint but diverges from research

| Area | Implementation | Research recommendation |
|------|----------------|-------------------------|
| **DB connection** | Custom `db/connection.py` + adapters; `get_conn()` calls `get_connection(None)` each time — **no connection caching**. New connection per request/rerun. | Cache connection as resource (e.g. `st.cache_resource` or `st.connection`). |
| **Config and Streamlit** | `config/settings.py` uses `st.secrets` in `get_setting()`. | Research allows env or secrets; blueprint/verification report flags config→Streamlit as a dependency violation for testability and non-Streamlit contexts. |

### 4.3 Where the implementation matches neither fully

- **Heavy load on every rerun:** `app.py` imports `ui.data.backend`, which eagerly imports the full `db` package, full `repository` package, and many services. So every rerun loads the entire backend tree; only the **screen** is lazy. Research stresses reducing rerun cost; the blueprint notes this as a known tradeoff.
- **Backend bootstrap on every rerun:** `bootstrap_backend_once()` is called from `app.py` on each run; it uses a `_BOOTSTRAPPED` flag so DB ensure and backfill run only once per process. So after the first run, bootstrap is a no-op; the cost is the import of backend and the one-time bootstrap on first load. Acceptable but worth documenting.

---

## 5. Misalignments

### 5.1 Implementation vs research

1. **Connection not cached as resource**  
   Research: cache engine/connection as resource; use one connection (or pool) per process.  
   Implementation: each `get_conn()` creates a new connection via `get_connection(None)`. Under load this can create many short-lived connections instead of reusing a pooled or cached connection.

2. **No use of `st.connection`**  
   Research recommends Streamlit’s `st.connection("sql")` for SQLAlchemy-based, cached connections and `conn.query()` with TTL for reads.  
   Implementation: custom adapter and repository with direct driver usage. This is valid but does not get Streamlit’s built-in connection caching or `conn.query()` caching.

3. **Config depends on Streamlit**  
   Research allows secrets from env or Streamlit.  
   Implementation: `get_setting()` uses `st.secrets`, so config is tied to Streamlit and is harder to use from API, scripts, or tests without a Streamlit context. The architecture report already marks this as a violation.

### 5.2 Implementation vs blueprint

1. **Missing `blueprint.md`**  
   Spec README states that `blueprint.md` at repo root holds canonical system identity and invariants. The file is absent, so those are only implied by other docs.

2. **Repository cross-coupling and rule in repository**  
   Blueprint/verification report: repository should be data-access only; business rules (e.g. confirmation invariant) should live in domain or service.  
   Implementation: `db/repository/risks.py` has `_ensure_confirmation_invariant` and is used from `db/repository/turnovers.py`; repository modules also call each other (e.g. risks→imports, tasks→turnovers, units→properties). So the blueprint’s ideal (no business rules in repository, minimal cross-repo coupling) is not fully met.

3. **Cache invalidation not a first-class contract**  
   Research: “treat cache invalidation as a first-class API.”  
   Implementation: invalidation is implemented (clear on write, and board-specific clear) but is not documented as a required contract (which writes must invalidate which caches) in the blueprint.

---

## 6. Missing Systems

Relative to the **research** and **blueprint**:

- **Canonical blueprint document:** A single `blueprint.md` (or equivalent) that states system identity, boundaries, and invariants. Referenced by spec but not present.
- **Connection resource caching:** A mechanism to cache the DB connection (or a pool) per process/session so that not every `get_conn()` creates a new connection. Research expects this; implementation does not provide it.
- **Explicit cache-invalidation contract:** A short spec or comment that defines which mutations must call which invalidation functions (e.g. “any turnover/task write must call `invalidate_board_caches()` or equivalent”) so future changes don’t leave caches stale.
- **Config free of Streamlit:** Optional but recommended: a way to resolve settings (including secrets) without importing Streamlit (e.g. env-only in non-UI entrypoints, or a small secrets loader that can be swapped for tests/API).

No “missing systems” in the sense of puzzle runtime, learning engine, or content systems — the project is an operations app; the research is about Streamlit/Supabase production patterns, and those are largely supported with the gaps above.

---

## 7. Architectural Risks

1. **Rerun cost and backend load**  
   Every rerun imports the full backend (db + repository + many services). As the codebase grows, rerun time and memory will increase unless backend loading is lazy or split (e.g. by screen or by feature). Research and blueprint both note the issue.

2. **Connection per call**  
   Without connection caching/pooling, high traffic or many concurrent users can exhaust DB connections or increase latency. Research explicitly recommends caching the connection as a resource.

3. **Config → Streamlit**  
   Any non-Streamlit entrypoint (API, scripts, tests) that needs settings must either mock Streamlit or duplicate config logic. This can lead to drift and bugs.

4. **Repository business rules**  
   Keeping `_ensure_confirmation_invariant` (and any similar rules) in the repository layer makes the “repository = data only” boundary fuzzy and can encourage more rule logic in the repository over time.

5. **Stale cache if invalidation is missed**  
   Without a written contract, new write paths might forget to call `invalidate_ui_caches()` or `invalidate_board_caches()`, leading to stale data in the UI until TTL expiry.

---

## 8. Improvement Opportunities

1. **Introduce connection caching**  
   Cache the result of `get_connection(None)` (or the underlying engine/session) with `st.cache_resource` in the UI path, or use Streamlit’s `st.connection("sql")` if switching to SQLAlchemy for the main app is acceptable. Ensure connection is closed or returned to pool on write/error as needed. This aligns with research and reduces connection churn.

2. **Add `blueprint.md`**  
   Create the referenced document at repo root: system name (DMRB), core entities (unit, turnover, task, etc.), layer boundaries, and key invariants (e.g. manual overrides preserved, import idempotency). Point spec/README and new contributors to it.

3. **Document cache invalidation contract**  
   In spec or in `ui/data/cache.py`, list which write operations must call `invalidate_ui_caches()` and which must call `invalidate_board_caches()`. Consider a single “after any data mutation” hook used by workflows so invalidation is centralized.

4. **Decouple config from Streamlit**  
   Make `get_setting()` use only environment variables when running outside Streamlit (e.g. detect `st` availability or pass a “secrets provider”). Use Streamlit secrets only when the app runs under Streamlit. This satisfies the blueprint’s desire for infrastructure not to depend on the UI framework.

5. **Move confirmation invariant out of repository**  
   Move “legal_confirmation requires confirmed_move_out_date” (and any related logic) into domain or a small service; repository should only persist and query. Call the invariant from the service that performs the update, then write risk/audit via repository. This aligns repository with “data only” and keeps the architecture report’s recommendations consistent.

6. **Consider lazy or split backend loading**  
   If rerun cost becomes an issue, consider loading db/repository and services only when first needed (e.g. when first `get_conn()` or first cache call runs), or loading a minimal “availability” stub and full backend only for screens that need it. This would be a larger change and should be weighed against complexity.

---

## 9. Conclusion

- **Research (Streamlit + Supabase production model):** The implementation follows it in most important ways: thin entrypoint, clear layering, TTL-based data caching, cache invalidation on writes, DB bootstrap at startup, parameterized queries, and Supabase transaction-mode compatibility. The main gaps are **connection not cached as a resource** and **config depending on Streamlit**.
- **Blueprint (spec + verification):** The codebase largely matches the intended layers and responsibilities (UI → application → services → repository/domain/infrastructure). Gaps are the **missing `blueprint.md`**, **repository holding a business rule and cross-repo coupling**, and **cache invalidation not being a first-class documented contract**.
- **Overall:** The implementation is **reasonably aligned** with both the research goals and the blueprint. Addressing connection caching, adding the blueprint document, documenting cache invalidation, and optionally decoupling config and moving the confirmation invariant out of the repository would strengthen alignment and maintainability. The human architect can use this report to decide which of these to prioritize.

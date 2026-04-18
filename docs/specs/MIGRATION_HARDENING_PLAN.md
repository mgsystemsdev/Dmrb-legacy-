# Migration Hardening Plan

Status: approved hardening overlay for the Streamlit-to-API migration plan.

This document does not replace the broader target-state blueprint. It corrects the migration plan so work stays anchored to the current repo and does not rebuild protections that already exist.

## Approved corrections

1. Do not rebuild the import idempotency guard. It already exists in `services/imports/orchestrator.py` and `services/import_service.py` for non-`AVAILABLE_UNITS` imports.
2. Treat `import_batch.status = FAILED` as the current dead-letter surface. Do not invent a second DLQ concept inside the legacy app.
3. Do not add Redis for UI filters. Stateless filters belong in URL query params; Redis is reserved for shared cache, rate limiting, and queue-adjacent concerns.
4. Do not introduce broad Pydantic models before an API boundary exists. Add typed boundary models when each FastAPI route is introduced.
5. Do not add `version: int` everywhere up front. Add optimistic-version fields only where a real schema or concurrency break requires them.
6. Do not trust `services/write_guard.py` as a global write lock. It only blocks writes inside a live Streamlit session. Global enforcement moves to the service/API boundary in Phase 6 via request-source policy.
7. Do not use `HX-Refresh`. For HTMX partial refresh behavior, the server must return the correct fragment and trigger contract explicitly.
8. Tailwind, when introduced, uses the standalone CLI binary. No `npm` build step is added for that decision.

## Phase 0 Go/No-Go gate

No migration code starts until these four questions are answered explicitly.

| Gate | Current repo evidence | Required answer | If unanswered |
|---|---|---|---|
| Redis availability | No Redis client, config, infra, or runtime wiring exists in this repo. Current cache is Streamlit-only (`st.cache_data`) and current architecture docs explicitly say Redis is missing. | Is Redis available in the target environment, and if so where is it provisioned and who owns it? | No-go for any phase that depends on shared cache, rate limiting, or Redis-backed coordination. |
| DB index ownership | Legacy schema and migrations already define operational indexes such as `import_batch_property_created_idx` in `db/schema.sql` and `db/migrations/001_initial.sql`. | Will target migrations be allowed to create equivalent indexes, and who verifies them in the target database? | No-go for performance-sensitive read-path or queue-state work that assumes those indexes exist. |
| Auth source | Current app supports `LEGACY_AUTH_SOURCE=env|db` in `config/settings.py` and `ui/auth.py`. No JWT or Supabase API auth exists in code. | What is the first API auth source: temporary legacy auth bridge, DB-backed legacy auth, or Supabase JWT from day one? | No-go for FastAPI auth middleware and request-context work. |
| Nginx availability | No Nginx config or reverse-proxy infra exists in this repo. | Is Nginx available as the traffic switch for rollout and rollback? If not, what exact edge/gateway replaces it? | No-go for any cutover story that claims instant rollback via proxy switch. |

`Go` means all four answers are concrete, owned, and written down. Anything else is `No-Go`.

## Invariants That Must Survive Migration

These are current-system invariants or guardrails that the migration cannot break.

| Invariant | Current owner | Failure mode if broken |
|---|---|---|
| Completed duplicate imports must be a no-op for non-`AVAILABLE_UNITS` files. | `services/imports/orchestrator.py`, `services/import_service.py` | The same file mutates operational state twice and operators lose trust in re-runs. |
| Batch creation, row writes, and turnover updates must commit atomically. | `services/imports/orchestrator.py`, `db/connection.py` | Partial imports leave orphaned rows or half-applied turnover state after an exception. |
| `FAILED` import batches remain visible and retryable; they are the current DLQ. | `services/import_service.py`, `db/repository/import_repository.py`, `db/schema.sql` (`import_batch`) | Failures disappear into logs only, with no operator-visible retry surface. |
| Every parsed import row must produce exactly one visible row outcome. | `services/imports/common.py`, `domain/import_outcomes.py` | Rows vanish silently and diagnostics stop matching source files. |
| A unit may not have more than one open turnover. | `services/turnover_service.py` | Duplicate active turnovers create conflicting tasks, readiness, and SLA state. |
| Manual overrides must beat conflicting import values until the import matches again. | `domain/manual_override.py`, `services/imports/available_units_service.py`, `services/turnover_service.py` | Imports overwrite operator decisions and destroy trust in manual correction workflows. |
| `PENDING_MOVE_INS` cannot be treated as a turnover bootstrap file. | `services/imports/orchestrator.py`, `docs/IMPORT_REBUILD_ORDER.md`, `tests/services/test_import_orchestrator_rebuild_order.py` | Move-in imports run against zero open turnovers and produce large conflict batches that look like successful processing. |

## Write-Guard Reality

Current behavior:

- `services/write_guard.py` checks the DB-writes toggle only when a Streamlit script context exists.
- Headless contexts such as tests, CLI, scripts, workers, and future API handlers are allowed by default.

Migration implication:

- The current write guard is a Streamlit-session convenience, not a system safety boundary.
- The global enforcement point must move to the service/API layer in Phase 6, with an explicit request-source contract such as `X-Request-Source`.
- Until that phase lands, any migration plan that claims a global write-off switch is inaccurate.

## Rollback Strategy

Rollback is an edge-routing problem, not an in-app feature flag.

- Streamlit stays alive through Phase 6.
- The proxy layer must be the switch: Nginx if available, otherwise the explicitly named edge substitute from Phase 0.
- Roll forward by shifting traffic to the new surface.
- Roll back by restoring traffic to Streamlit without requiring data rollback for unchanged routes.
- If there is no reversible proxy/gateway switch, the plan is not hardened enough to claim safe cutover.

## Corrected Dependency Rule

- Phase 4 is blocked until Phase 0 confirms Redis availability.
- Do not front-load Redis-shaped abstractions into earlier phases just to make the diagram look cleaner.
- Route, service, and worker work may proceed only where they do not depend on an unanswered Redis decision.

## Migration Contract For Tests

After every phase:

```bash
pytest tests/
```

This is the migration contract, not an optional cleanup step.

Notes:

- `CLAUDE.md` states that service tests require a live `DATABASE_URL`.
- A phase is not complete until the full test suite passes in an environment that matches that requirement.

## What This Document Prevents

- Rebuilding protections that already exist.
- Calling speculative infrastructure "done" when the environment answers are still unknown.
- Smuggling global safety claims into Streamlit-local mechanisms.
- Starting Redis-dependent work before Redis is real.

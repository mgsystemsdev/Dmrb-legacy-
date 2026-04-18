# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Run Commands

```bash
# App
streamlit run app.py

# Tests
pytest tests/
pytest tests/domain/test_lifecycle.py   # single file
pytest tests/services/test_board.py     # single file

# Nightly automation (can backtest with --date)
python scripts/run_midnight_automation.py
python scripts/run_midnight_automation.py --date 2026-03-16
```

No build step — pure Python. Schema is bootstrapped automatically on first run via `ui/data/backend.py` → `db/migration_runner.py`.

### Multi-checkout (legacy vs prod)

If you have **two folders** (dev clone + production), they are separate apps: **different** `DATABASE_URL` and `.streamlit/secrets.toml` per tree. For the **task dashboard** (`agents` CLI), use **one slug per folder** (e.g. `dmrb-legacy` here, `dmrb-prod` in prod) and `agents push --slug …` from the matching directory. Details: `AGENTS.md` → *Multi-checkout and task dashboard*.

## Environment Variables

`DATABASE_URL` is mandatory. All others are optional.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | — | PostgreSQL connection string |
| `AUTH_DISABLED` | false | Bypass login in local dev |
| `LEGACY_AUTH_SOURCE` | `env` | `env` (APP_*/VALIDATOR_* vars) or `db` (Argon2 from `app_user` table) |
| `APP_USERNAME`, `APP_PASSWORD` | — | Admin credentials when source=env |
| `VALIDATOR_USERNAME`, `VALIDATOR_PASSWORD` | — | Validator credentials when source=env |
| `OPENAI_API_KEY` | — | Required for AI agent screen only |
| `STRICT_IMPORT_REBUILD_ORDER` | false | Fail imports if report type order is violated |

Streamlit secrets (`~/.streamlit/secrets.toml`) are an alternative to env vars — `config/settings.py` resolves both.

## Architecture

### Layer Boundaries (strict — do not violate)

```
UI (ui/screens/, ui/components/)
    ↓ calls
Services (services/)              — orchestration, workflow logic
    ↓ calls
Repositories (db/repository/)     — all DB access, one module per entity
    ↓ uses
Domain (domain/)                  — pure logic, no I/O, no DB
```

Services are the only callers of repositories. Screens never query the DB directly.

### Request / Data Flow

**Board load** (every Streamlit rerun):
```
board.py → board_service.get_board()
    → board_reconciliation.run()          # healing: missing turnovers, task backfill
    → lifecycle_transition_service        # automated state transitions
    → repositories (turnovers, tasks, units, …)
    → domain/priority_engine.py           # sort/score
    → domain/readiness.py                 # task completion status
    → returns structured board rows
```

**CSV import pipeline:**
```
import_console.py → import_service.py → services/imports/orchestrator.py
    → file_validator + schema_validator
    → route by report type (MOVE_OUTS | PENDING_MOVE_INS | AVAILABLE_UNITS | PENDING_FAS)
    → type-specific service (move_outs_service.py, etc.)
    → db/repository/*
```

**Import rebuild order matters** — see `docs/IMPORT_REBUILD_ORDER.md`. MOVE_OUTS must run before AVAILABLE_UNITS; order violations break reconciliation.

### Routing

`app.py` bootstraps DB and session state, then calls `ui/router.py`. The router dispatches to one of 14 screens based on `st.session_state["current_page"]`. There is no URL routing — all navigation is via sidebar widget state.

### Key Domain Concepts

- **Turnover lifecycle** (`domain/turnover_lifecycle.py`): `PRE_NOTICE → ON_NOTICE → VACANT_NOT_READY → VACANT_READY → MOVE_IN_READY → CLOSED`. State is derived from dates + manual overrides — it is never stored directly.
- **Readiness** (`domain/readiness.py`): `READY | IN_PROGRESS | BLOCKED | NOT_STARTED | NO_TASKS` — derived from task completion at board load.
- **Priority engine** (`domain/priority_engine.py`): urgency scoring based on SLA breach, inspection delays, move-in danger, agreement violations.
- **Board reconciliation** (`services/board_reconciliation.py`): runs on every board load; creates missing turnovers, backfills tasks, resolves availability status conflicts. It is idempotent and safe to re-run.

### Database

- `db/schema.sql` — base DDL (9 core tables + 8+ supporting tables, triggers for `updated_at` and append-only enforcement)
- `db/migration_runner.py` — idempotent bootstrapper; checks table/column existence before applying each of 14 incremental migrations
- `db/connection.py` — singleton psycopg2 connection; `transaction()` context manager for atomic writes
- `db/repository/` — one file per entity; all SQL lives here; repositories return plain dicts

### Testing Notes

- `tests/domain/` — pure unit tests, no DB needed
- `tests/services/` — may hit the DB; `tests/services/conftest.py` auto-patches the write guard so service tests can write
- Domain tests are safe to run anywhere; service tests require a live `DATABASE_URL`

## Key Files

| File | Purpose |
|------|---------|
| `services/board_service.py` | Centerpiece: assembles the full operational board (716 lines — touch carefully) |
| `services/board_reconciliation.py` | Healing logic that runs on every board load |
| `services/imports/orchestrator.py` | CSV import pipeline entry point |
| `domain/turnover_lifecycle.py` | Turnover state machine — pure logic |
| `db/connection.py` | DB singleton + `transaction()` context manager |
| `db/migration_runner.py` | Idempotent schema bootstrapper |
| `config/settings.py` | Env/secrets resolution |
| `ui/router.py` | Page dispatcher |
| `docs/LEGACY_APP_FLOW.md` | Mermaid flow diagrams for all major paths |
| `docs/IMPORT_REBUILD_ORDER.md` | Operational law for import sequencing |
| `docs/DMRB_master_blueprint.md` | Master spec — entity definitions, state rules, business agreements |
| `AGENTS.md` | Multi-checkout / dashboard slug conventions |

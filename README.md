# DMRB Legacy

**The DMRB (Digital Make Ready Board)** — a FastAPI + React application for **apartment turnover** operations: board views, task pipelines, CSV imports from property-management reports, exports, optional AI assistance, and work-order validation workflows. Data lives in **PostgreSQL** (no ORM; repositories + raw SQL).

## Requirements

- Python 3.11+ (3.13 used in development)
- PostgreSQL database and a `DATABASE_URL` connection string

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Set `DATABASE_URL` in the environment (see `config/settings.py` for all supported keys). Do not commit secrets.

```bash
cd frontend && npm install && npm run build
cd ..
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## Commands

| Action | Command |
|--------|---------|
| Build frontend | `cd frontend && npm install && npm run build` |
| Run app | `uvicorn api.main:app --reload --host 0.0.0.0 --port 8000` |
| Tests | `pytest tests/` |
| Midnight automation (scheduled jobs) | `python scripts/run_midnight_automation.py` (optional `--date YYYY-MM-DD`) |

## Configuration

Mandatory: **`DATABASE_URL`**.

Common optional variables: `AUTH_DISABLED`, `LEGACY_AUTH_SOURCE` (`env` \| `db`), `APP_USERNAME` / `APP_PASSWORD`, `VALIDATOR_USERNAME` / `VALIDATOR_PASSWORD`, `OPENAI_API_KEY` (AI Agent screen), `STRICT_IMPORT_REBUILD_ORDER`.

Full table and architecture rules: **[CLAUDE.md](CLAUDE.md)**. Operator-facing flow diagrams: **[docs/LEGACY_APP_FLOW.md](docs/LEGACY_APP_FLOW.md)**.

## Project layout

| Path | Purpose |
|------|---------|
| `api/main.py` | FastAPI entrypoint + SPA host |
| `frontend/` | React SPA |
| `ui_archive/` | Archived Streamlit reference code |
| `services/` | Orchestration and workflows |
| `db/repository/` | Database access |
| `domain/` | Pure business logic |
| `db/migrations/` | Incremental schema migrations (applied at startup) |

## Documentation

- **[docs/IMPORT_REBUILD_ORDER.md](docs/IMPORT_REBUILD_ORDER.md)** — import sequencing and rebuild contract
- **[AGENTS.md](AGENTS.md)** — notes for AI assistants and multi-checkout (dev vs prod)
- **[HARDENED_MIGRATION_PLAN.md](HARDENED_MIGRATION_PLAN.md)** — migration / hardening planning

## License

See the [`LICENSE`](LICENSE) file in the repository root for terms of use.

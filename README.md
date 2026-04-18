# DMRB Legacy

**The DMRB (Digital Make Ready Board)** — a Streamlit application for **apartment turnover** operations: board views, task pipelines, CSV imports from property-management reports, exports, optional AI assistance, and work-order validation workflows. Data lives in **PostgreSQL** (no ORM; repositories + raw SQL).

## Requirements

- Python 3.11+ (3.13 used in development)
- PostgreSQL database and a `DATABASE_URL` connection string

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Set `DATABASE_URL` in the environment or in `.streamlit/secrets.toml` (see `config/settings.py` for all supported keys). Do not commit secrets.

```bash
streamlit run app.py
```

## Commands

| Action | Command |
|--------|---------|
| Run app | `streamlit run app.py` |
| Tests | `pytest tests/` |
| Midnight automation (scheduled jobs) | `python scripts/run_midnight_automation.py` (optional `--date YYYY-MM-DD`) |

## Configuration

Mandatory: **`DATABASE_URL`**.

Common optional variables: `AUTH_DISABLED`, `LEGACY_AUTH_SOURCE` (`env` \| `db`), `APP_USERNAME` / `APP_PASSWORD`, `VALIDATOR_USERNAME` / `VALIDATOR_PASSWORD`, `OPENAI_API_KEY` (AI Agent screen), `STRICT_IMPORT_REBUILD_ORDER`.

Full table and architecture rules: **[CLAUDE.md](CLAUDE.md)**. Operator-facing flow diagrams: **[docs/LEGACY_APP_FLOW.md](docs/LEGACY_APP_FLOW.md)**.

## Project layout

| Path | Purpose |
|------|---------|
| `app.py` | Entrypoint |
| `ui/screens/` | Streamlit pages |
| `ui/router.py` | Page dispatch |
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

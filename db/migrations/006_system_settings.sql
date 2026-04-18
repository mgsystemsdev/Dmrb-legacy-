-- Migration 006: System settings — persistent key/value (e.g. enable_db_write).
-- Idempotent — safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Default: DB writes disabled until admin enables
INSERT INTO system_settings (key, value, updated_at)
VALUES ('enable_db_write', 'false', NOW())
ON CONFLICT (key) DO NOTHING;

COMMIT;

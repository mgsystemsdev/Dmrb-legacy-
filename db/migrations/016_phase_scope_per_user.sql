-- Migration 016: Allow phase_scope rows per (app user, property) in addition
-- to the legacy property-wide row (user_id NULL). Idempotent.

BEGIN;

-- Legacy scope is the row with user_id IS NULL (one per property).
UPDATE phase_scope SET user_id = NULL WHERE user_id IS NOT NULL;

ALTER TABLE phase_scope DROP CONSTRAINT IF EXISTS phase_scope_property_unique;

CREATE UNIQUE INDEX IF NOT EXISTS phase_scope_property_global_uq
    ON phase_scope (property_id) WHERE user_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS phase_scope_user_property_uq
    ON phase_scope (user_id, property_id) WHERE user_id IS NOT NULL;

COMMIT;

-- Track when a conflict import row has been resolved by the manager.
ALTER TABLE import_row
    ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;

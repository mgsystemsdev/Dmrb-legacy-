-- Migration 013: Add W/D workflow tracking columns to turnover
-- Adds wd_notified_at and wd_installed_at for persistent W/D tracking.
-- Constraint enforces that installed cannot be set without notified.

ALTER TABLE turnover ADD COLUMN IF NOT EXISTS wd_notified_at TIMESTAMPTZ;
ALTER TABLE turnover ADD COLUMN IF NOT EXISTS wd_installed_at TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'turnover_wd_install_requires_notify'
    ) THEN
        ALTER TABLE turnover
            ADD CONSTRAINT turnover_wd_install_requires_notify
            CHECK (wd_installed_at IS NULL OR wd_notified_at IS NOT NULL);
    END IF;
END $$;

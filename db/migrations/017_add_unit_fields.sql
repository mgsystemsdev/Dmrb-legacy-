-- Add missing columns required by Unit Master import
-- Safe for re-runs (idempotent)

ALTER TABLE unit
ADD COLUMN IF NOT EXISTS floor_plan TEXT;

ALTER TABLE unit
ADD COLUMN IF NOT EXISTS gross_sq_ft INTEGER;

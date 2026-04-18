-- Add fields required by the import pipeline (Move Outs service).

-- Tracks how many consecutive Move Outs imports this turnover's unit
-- has been absent from.  Auto-cancel fires at count >= 2.
ALTER TABLE turnover
    ADD COLUMN IF NOT EXISTS missing_moveout_count INTEGER NOT NULL DEFAULT 0;

-- Timestamp of a manual override on scheduled_move_out_date.
-- When set, the import pipeline will not overwrite the value unless
-- the report matches.
ALTER TABLE turnover
    ADD COLUMN IF NOT EXISTS move_out_manual_override_at TIMESTAMPTZ;

-- Timestamp of a manual override on move_in_date.
ALTER TABLE turnover
    ADD COLUMN IF NOT EXISTS move_in_manual_override_at TIMESTAMPTZ;

-- Timestamp of a manual override on report_ready_date.
ALTER TABLE turnover
    ADD COLUMN IF NOT EXISTS ready_manual_override_at TIMESTAMPTZ;

-- Timestamp of a manual override on availability_status.
ALTER TABLE turnover
    ADD COLUMN IF NOT EXISTS status_manual_override_at TIMESTAMPTZ;

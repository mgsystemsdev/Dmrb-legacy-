-- Add completed_date to task for the new completion-date workflow.
-- Stores the calendar date of official task completion; initially NULL for all tasks.

ALTER TABLE task ADD COLUMN IF NOT EXISTS completed_date DATE;

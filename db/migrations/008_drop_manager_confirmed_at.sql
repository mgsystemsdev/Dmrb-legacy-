-- Remove manager confirmation from task. Completion is determined solely by
-- execution_status = 'COMPLETED' and vendor_completed_at.

ALTER TABLE task DROP CONSTRAINT IF EXISTS task_manager_confirmed_requires_completion;
ALTER TABLE task DROP COLUMN IF EXISTS manager_confirmed_at;

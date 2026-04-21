-- Phase: Task FSM States & Constraints

-- 1. Add new columns
ALTER TABLE task_template ADD COLUMN skip_allowed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE task ADD COLUMN skip_allowed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE task ADD COLUMN blocked_reason TEXT;

-- 2. Drop old constraints BEFORE updating data
ALTER TABLE task DROP CONSTRAINT task_execution_status_valid;
ALTER TABLE task DROP CONSTRAINT task_completed_requires_vendor_completed_at;

-- 3. Update execution_status values
-- Map existing statuses to new ones
UPDATE task SET execution_status = 'SCHEDULED' WHERE execution_status = 'NOT_STARTED';
UPDATE task SET execution_status = 'COMPLETE' WHERE execution_status = 'COMPLETED';

-- 4. Add new constraints
ALTER TABLE task ADD CONSTRAINT task_execution_status_valid CHECK (
    execution_status IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETE', 'SKIPPED', 'BLOCKED')
);

ALTER TABLE task ADD CONSTRAINT task_completed_requires_vendor_completed_at CHECK (
    execution_status <> 'COMPLETE' OR vendor_completed_at IS NOT NULL
);

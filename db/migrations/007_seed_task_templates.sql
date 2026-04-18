-- Migration 007: Seed default task templates for every existing phase.
-- Idempotent — inserts only when no active template exists for (phase_id, task_type).
-- Ensures turnovers get auto-created tasks; run once after 006.

BEGIN;

INSERT INTO task_template (
    property_id, phase_id, task_type, offset_days_from_move_out,
    sort_order, required, blocking, is_active
)
SELECT p.property_id, p.phase_id, 'INSPECT', 1, 0, true, true, true
FROM phase p
WHERE NOT EXISTS (
    SELECT 1 FROM task_template t
    WHERE t.phase_id = p.phase_id AND t.task_type = 'INSPECT' AND t.is_active = TRUE
);

INSERT INTO task_template (
    property_id, phase_id, task_type, offset_days_from_move_out,
    sort_order, required, blocking, is_active
)
SELECT p.property_id, p.phase_id, 'CARPET_BID', 2, 1, true, true, true
FROM phase p
WHERE NOT EXISTS (
    SELECT 1 FROM task_template t
    WHERE t.phase_id = p.phase_id AND t.task_type = 'CARPET_BID' AND t.is_active = TRUE
);

INSERT INTO task_template (
    property_id, phase_id, task_type, offset_days_from_move_out,
    sort_order, required, blocking, is_active
)
SELECT p.property_id, p.phase_id, 'MAKE_READY_BID', 2, 2, true, true, true
FROM phase p
WHERE NOT EXISTS (
    SELECT 1 FROM task_template t
    WHERE t.phase_id = p.phase_id AND t.task_type = 'MAKE_READY_BID' AND t.is_active = TRUE
);

INSERT INTO task_template (
    property_id, phase_id, task_type, offset_days_from_move_out,
    sort_order, required, blocking, is_active
)
SELECT p.property_id, p.phase_id, 'PAINT', 3, 3, true, true, true
FROM phase p
WHERE NOT EXISTS (
    SELECT 1 FROM task_template t
    WHERE t.phase_id = p.phase_id AND t.task_type = 'PAINT' AND t.is_active = TRUE
);

INSERT INTO task_template (
    property_id, phase_id, task_type, offset_days_from_move_out,
    sort_order, required, blocking, is_active
)
SELECT p.property_id, p.phase_id, 'MAKE_READY', 5, 4, true, true, true
FROM phase p
WHERE NOT EXISTS (
    SELECT 1 FROM task_template t
    WHERE t.phase_id = p.phase_id AND t.task_type = 'MAKE_READY' AND t.is_active = TRUE
);

INSERT INTO task_template (
    property_id, phase_id, task_type, offset_days_from_move_out,
    sort_order, required, blocking, is_active
)
SELECT p.property_id, p.phase_id, 'HOUSEKEEPING', 6, 5, true, true, true
FROM phase p
WHERE NOT EXISTS (
    SELECT 1 FROM task_template t
    WHERE t.phase_id = p.phase_id AND t.task_type = 'HOUSEKEEPING' AND t.is_active = TRUE
);

INSERT INTO task_template (
    property_id, phase_id, task_type, offset_days_from_move_out,
    sort_order, required, blocking, is_active
)
SELECT p.property_id, p.phase_id, 'CARPET_CLEAN', 6, 6, true, true, true
FROM phase p
WHERE NOT EXISTS (
    SELECT 1 FROM task_template t
    WHERE t.phase_id = p.phase_id AND t.task_type = 'CARPET_CLEAN' AND t.is_active = TRUE
);

INSERT INTO task_template (
    property_id, phase_id, task_type, offset_days_from_move_out,
    sort_order, required, blocking, is_active
)
SELECT p.property_id, p.phase_id, 'FINAL_WALK', 7, 7, true, true, true
FROM phase p
WHERE NOT EXISTS (
    SELECT 1 FROM task_template t
    WHERE t.phase_id = p.phase_id AND t.task_type = 'FINAL_WALK' AND t.is_active = TRUE
);

INSERT INTO task_template (
    property_id, phase_id, task_type, offset_days_from_move_out,
    sort_order, required, blocking, is_active
)
SELECT p.property_id, p.phase_id, 'QUALITY_CONTROL', 8, 8, true, true, true
FROM phase p
WHERE NOT EXISTS (
    SELECT 1 FROM task_template t
    WHERE t.phase_id = p.phase_id AND t.task_type = 'QUALITY_CONTROL' AND t.is_active = TRUE
);

COMMIT;

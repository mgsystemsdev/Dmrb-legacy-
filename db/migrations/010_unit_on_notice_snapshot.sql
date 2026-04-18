-- Phase 5: Import Automation Layer — store On Notice units (no turnover yet) for midnight automation.
-- When Available Units import sees status=On Notice and no open turnover, it IGNORED and upserts here.
-- Midnight automation creates turnover when available_date <= today and removes the row.

CREATE TABLE IF NOT EXISTS unit_on_notice_snapshot (
    property_id BIGINT NOT NULL REFERENCES property(property_id) ON DELETE CASCADE,
    unit_id BIGINT NOT NULL,
    available_date DATE NOT NULL,
    move_in_ready_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (property_id, unit_id),
    CONSTRAINT unit_on_notice_snapshot_unit_fk
        FOREIGN KEY (property_id, unit_id)
        REFERENCES unit(property_id, unit_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS unit_on_notice_snapshot_available_date_idx
    ON unit_on_notice_snapshot (property_id, available_date);

DROP TRIGGER IF EXISTS unit_on_notice_snapshot_set_updated_at ON unit_on_notice_snapshot;
CREATE TRIGGER unit_on_notice_snapshot_set_updated_at
    BEFORE UPDATE ON unit_on_notice_snapshot
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE unit_on_notice_snapshot IS 'On Notice units from Available Units import with no turnover; automation creates turnover when available_date arrives.';

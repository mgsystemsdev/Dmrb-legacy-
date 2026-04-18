"""Integration tests: default task templates on phase creation (007 parity)."""
from __future__ import annotations

import uuid
from datetime import date


from db.repository import task_repository
from services import property_service, task_service, turnover_service


_EXPECTED_TYPES = frozenset({
    "INSPECT",
    "CARPET_BID",
    "MAKE_READY_BID",
    "PAINT",
    "MAKE_READY",
    "HOUSEKEEPING",
    "CARPET_CLEAN",
    "FINAL_WALK",
    "QUALITY_CONTROL",
})


def test_create_phase_seeds_default_templates():
    """New phase via property_service.create_phase gets full pipeline templates."""
    suffix = uuid.uuid4().hex[:10]
    phase_code = f"SEED_{suffix}"
    phase = property_service.create_phase(1, phase_code, name="template seed test")
    phase_id = int(phase["phase_id"])

    assert task_service.has_templates_for_phase(phase_id)
    templates = task_repository.get_templates_by_phase(phase_id, active_only=True)
    assert len(templates) == len(_EXPECTED_TYPES)
    assert {t["task_type"] for t in templates} == _EXPECTED_TYPES


def test_ensure_default_templates_for_phase_is_idempotent():
    """Second call inserts zero additional active rows."""
    suffix = uuid.uuid4().hex[:10]
    phase = property_service.create_phase(1, f"IDEM_{suffix}")
    phase_id = int(phase["phase_id"])

    n = task_service.ensure_default_templates_for_phase(1, phase_id)
    assert n == 0
    templates = task_repository.get_templates_by_phase(phase_id, active_only=True)
    assert len(templates) == 9


def test_create_turnover_instantiates_pipeline_for_import_created_phase():
    """Unit on a freshly created phase receives all template-driven tasks."""
    suffix = uuid.uuid4().hex[:10]
    phase = property_service.create_phase(1, f"TUR_{suffix}")
    phase_id = int(phase["phase_id"])

    identity = f"1|UNIT-TPL-{suffix}"
    unit = property_service.create_unit(
        1,
        f"UNIT-TPL-{suffix}",
        f"UNIT-TPL-{suffix}",
        identity,
        phase_id=phase_id,
    )
    move_out = date(2025, 1, 15)
    turnover = turnover_service.create_turnover(
        1,
        int(unit["unit_id"]),
        move_out,
        actor="test",
    )

    tasks = task_repository.get_by_turnover(int(turnover["turnover_id"]))
    types = {t["task_type"] for t in tasks}
    assert types == _EXPECTED_TYPES
    assert len(tasks) == 9

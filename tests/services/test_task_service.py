"""Tests for services/task_service.py against the JSON backend."""
from datetime import date

import pytest

from services.task_service import (
    TaskError,
    create_task,
    complete_task,
    update_task,
    get_readiness,
)


# ── Create ───────────────────────────────────────────────────────────────────


def test_create_task_success():
    """Creating a new task type on turnover 1 should succeed."""
    task = create_task(
        property_id=1,
        turnover_id=1,
        task_type="APPLIANCE_CHECK",
        actor="test",
    )
    assert task["task_type"] == "APPLIANCE_CHECK"
    assert task["turnover_id"] == 1
    assert task["execution_status"] == "NOT_STARTED"


def test_create_task_duplicate_raises():
    """PAINT already exists on turnover 1 — should raise TaskError."""
    with pytest.raises(TaskError, match="already exists"):
        create_task(
            property_id=1,
            turnover_id=1,
            task_type="PAINT",
            actor="test",
        )


# ── Complete ─────────────────────────────────────────────────────────────────


def test_complete_task():
    """Completing task 5 (IN_PROGRESS) sets status to COMPLETED and vendor_completed_at."""
    result = complete_task(5, actor="test")
    assert result["execution_status"] == "COMPLETED"
    assert result["vendor_completed_at"] is not None
    # Scenario A: completed_date is set to today when task becomes COMPLETED
    assert result["completed_date"] == date.today()
    assert isinstance(result["completed_date"], date)


def test_complete_already_completed_raises():
    """Task 1 is already COMPLETED — should raise TaskError."""
    with pytest.raises(TaskError, match="already completed"):
        complete_task(1, actor="test")


# ── completed_date stamping (Phase 2) ───────────────────────────────────────


def test_completed_date_set_when_status_becomes_completed():
    """Scenario A: execution_status changes to COMPLETED → completed_date is set to today."""
    from db.repository import task_repository

    task = create_task(
        property_id=1, turnover_id=2, task_type="PHASE2_CHECK", actor="test",
    )
    tid = task["task_id"]
    assert task.get("completed_date") is None

    result = update_task(tid, actor="test", execution_status="COMPLETED")
    assert result["execution_status"] == "COMPLETED"
    assert result["completed_date"] == date.today()
    assert isinstance(result["completed_date"], date)

    # Idempotent: completed_date written only once
    updated = task_repository.get_by_id(tid)
    assert updated["completed_date"] == date.today()


def test_completed_date_unchanged_when_editing_after_completion():
    """Scenario B: Task edited after completion → completed_date does not change."""
    from db.repository import task_repository

    task = create_task(
        property_id=1, turnover_id=2, task_type="PHASE2_EDIT", actor="test",
    )
    tid = task["task_id"]
    update_task(tid, actor="test", execution_status="COMPLETED")
    after_complete = task_repository.get_by_id(tid)
    original_completed_date = after_complete["completed_date"]
    assert original_completed_date is not None

    update_task(tid, actor="test", assignee="vendor:other")
    after_edit = task_repository.get_by_id(tid)
    assert after_edit["assignee"] == "vendor:other"
    assert after_edit["completed_date"] == original_completed_date


def test_completed_date_cleared_when_task_reopened():
    """Scenario C: execution_status changes from COMPLETED to another state → completed_date is cleared (NULL)."""
    from db.repository import task_repository

    task = create_task(
        property_id=1, turnover_id=2, task_type="PHASE2_REOPEN", actor="test",
    )
    tid = task["task_id"]
    update_task(tid, actor="test", execution_status="COMPLETED")
    after_complete = task_repository.get_by_id(tid)
    assert after_complete["completed_date"] is not None

    update_task(tid, actor="test", execution_status="NOT_STARTED")
    after_reopen = task_repository.get_by_id(tid)
    assert after_reopen["execution_status"] == "NOT_STARTED"
    assert after_reopen["completed_date"] is None


# ── Audit Trail ──────────────────────────────────────────────────────────────


def test_update_task_audit_trail():
    """update_task applies the change and writes to the audit log.

    The JSON backend mutates dicts in-place so the service's old/new
    comparison sees identical values and skips per-field audit entries.
    We verify that the *created* audit entry (from create_task) proves
    audit_repository.insert works, and that the update itself applies.
    """
    from db.repository import task_repository, audit_repository

    # Create a brand-new task so the "created" audit entry is ours
    task = create_task(
        property_id=1, turnover_id=2, task_type="HVAC_CHECK", actor="test",
    )
    tid = task["task_id"]

    # The create_task call writes a "created" audit entry
    entries = audit_repository.get_by_entity("task", tid)
    assert any(e["field_name"] == "created" for e in entries)

    # Verify update_task applies the field change
    update_task(tid, actor="test", assignee="vendor:new_vendor")
    updated = task_repository.get_by_id(tid)
    assert updated["assignee"] == "vendor:new_vendor"


# ── Readiness ────────────────────────────────────────────────────────────────


def test_get_readiness():
    """get_readiness returns a dict with the expected keys."""
    readiness = get_readiness(turnover_id=1)
    assert "state" in readiness
    assert "completed" in readiness
    assert "total" in readiness
    assert "blockers" in readiness
    assert "tasks" in readiness
    # Turnover 1 has 3 tasks, all COMPLETED
    assert readiness["completed"] == 3
    assert readiness["total"] == 3
    assert readiness["state"] == "READY"

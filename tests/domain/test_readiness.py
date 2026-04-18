"""Tests for domain.readiness — pure readiness state computation."""

from __future__ import annotations

from domain.readiness import (
    BLOCKED,
    IN_PROGRESS,
    NO_TASKS,
    NOT_STARTED,
    READY,
    blocking_tasks,
    completion_ratio,
    readiness_state,
)


def _task(
    task_type="PAINT",
    execution_status="NOT_STARTED",
    required=True,
    blocking=True,
    **kw,
):
    return {
        "task_id": 1,
        "task_type": task_type,
        "execution_status": execution_status,
        "required": required,
        "blocking": blocking,
        "vendor_completed_at": None,
        **kw,
    }


class TestReadinessState:
    def test_no_tasks_returns_no_tasks(self):
        assert readiness_state([]) == NO_TASKS

    def test_all_required_blocking_completed_returns_ready(self):
        tasks = [
            _task(execution_status="COMPLETED"),
            _task(task_type="CLEAN", execution_status="COMPLETED"),
        ]
        assert readiness_state(tasks) == READY

    def test_no_blocking_tasks_returns_ready(self):
        tasks = [
            _task(required=True, blocking=False, execution_status="NOT_STARTED"),
            _task(task_type="CLEAN", required=True, blocking=False),
        ]
        assert readiness_state(tasks) == READY

    def test_some_started_with_blockers_returns_blocked(self):
        tasks = [
            _task(execution_status="COMPLETED"),
            _task(task_type="CLEAN", execution_status="SCHEDULED"),
            _task(task_type="INSPECT", execution_status="NOT_STARTED"),
        ]
        assert readiness_state(tasks) == BLOCKED

    def test_nothing_started_returns_not_started(self):
        tasks = [
            _task(execution_status="NOT_STARTED"),
            _task(task_type="CLEAN", execution_status="NOT_STARTED"),
        ]
        assert readiness_state(tasks) == NOT_STARTED

    def test_some_started_all_blocking_complete_returns_ready(self):
        """All required+blocking COMPLETED; one non-blocking IN_PROGRESS -> READY (not IN_PROGRESS)."""
        tasks = [
            _task(execution_status="COMPLETED"),
            _task(task_type="CLEAN", execution_status="COMPLETED"),
            _task(task_type="INSPECT", execution_status="IN_PROGRESS", blocking=False),
        ]
        assert readiness_state(tasks) == READY

    def test_non_blocking_incomplete_but_all_blocking_completed_returns_ready(self):
        """Case 6: Non-blocking incomplete but all blocking completed -> READY."""
        tasks = [
            _task(execution_status="COMPLETED"),
            _task(task_type="CLEAN", execution_status="COMPLETED"),
            _task(task_type="OPTIONAL", required=False, blocking=False, execution_status="NOT_STARTED"),
        ]
        assert readiness_state(tasks) == READY


class TestBlockingTasks:
    def test_blocking_tasks_returns_incomplete_required_blocking(self):
        tasks = [
            _task(execution_status="COMPLETED"),
            _task(task_type="CLEAN", execution_status="SCHEDULED"),
            _task(task_type="OPTIONAL", required=False, blocking=False),
            _task(task_type="NON_BLOCK", required=True, blocking=False),
        ]
        result = blocking_tasks(tasks)
        assert len(result) == 1
        assert result[0]["task_type"] == "CLEAN"


class TestCompletionRatio:
    def test_completion_ratio(self):
        tasks = [
            _task(execution_status="COMPLETED"),
            _task(task_type="CLEAN", execution_status="SCHEDULED"),
            _task(task_type="OPTIONAL", required=False, execution_status="NOT_STARTED"),
        ]
        completed, total = completion_ratio(tasks)
        assert completed == 1
        assert total == 2

    def test_completion_ratio_zero_tasks(self):
        completed, total = completion_ratio([])
        assert completed == 0
        assert total == 0

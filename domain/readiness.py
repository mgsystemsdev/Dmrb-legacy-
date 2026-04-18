"""Readiness state computation.

Determines whether a turnover's task pipeline is complete,
blocked, or in progress.  Pure functions only.
"""

from __future__ import annotations


# ── Readiness States ─────────────────────────────────────────────────────────

READY = "READY"
BLOCKED = "BLOCKED"
IN_PROGRESS = "IN_PROGRESS"
NOT_STARTED = "NOT_STARTED"
NO_TASKS = "NO_TASKS"


def readiness_state(tasks: list[dict]) -> str:
    """Compute aggregate readiness from a turnover's task list.

    Args:
        tasks: list of task dicts as returned by task_repository.get_by_turnover.

    Returns:
        One of the readiness constants above.
    """
    if not tasks:
        return NO_TASKS

    blocking = [t for t in tasks if t.get("required") and t.get("blocking")]
    if not blocking:
        return READY

    all_done = all(t["execution_status"] == "COMPLETED" for t in blocking)
    if all_done:
        return READY

    any_started = any(
        t["execution_status"] in ("SCHEDULED", "IN_PROGRESS", "COMPLETED")
        for t in blocking
    )
    if any_started:
        has_block = any(
            t["execution_status"] != "COMPLETED" and t.get("blocking")
            for t in tasks
            if t.get("required")
        )
        return BLOCKED if has_block else IN_PROGRESS

    return NOT_STARTED


def blocking_tasks(tasks: list[dict]) -> list[dict]:
    """Return the subset of tasks that are required, blocking, and incomplete."""
    return [
        t for t in tasks
        if t.get("required")
        and t.get("blocking")
        and t["execution_status"] != "COMPLETED"
    ]


def completion_ratio(tasks: list[dict]) -> tuple[int, int]:
    """Return (completed_count, total_required_count)."""
    required = [t for t in tasks if t.get("required")]
    completed = [t for t in required if t["execution_status"] == "COMPLETED"]
    return len(completed), len(required)


def next_pending_task(tasks: list[dict]) -> dict | None:
    """Return the first required task that is not yet completed, by sort order.

    Assumes tasks are ordered by task_type from the repository.
    """
    for t in tasks:
        if t.get("required") and t["execution_status"] != "COMPLETED":
            return t
    return None

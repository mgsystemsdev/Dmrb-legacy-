"""Task service — coordinates task lifecycle and template instantiation.

Enforces invariants:
  - Task type uniqueness per turnover.
  - Completion requires vendor_completed_at.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from db.repository import task_repository, turnover_repository, audit_repository
from domain import readiness as readiness_domain
from services.write_guard import check_writes_enabled


class TaskError(Exception):
    pass


# Default pipeline templates for new phases — must stay aligned with
# db/migrations/007_seed_task_templates.sql (task_type, offset_days, sort_order).
_DEFAULT_PIPELINE_TEMPLATES: tuple[tuple[str, int, int], ...] = (
    ("INSPECT", 1, 0),
    ("CARPET_BID", 2, 1),
    ("MAKE_READY_BID", 2, 2),
    ("PAINT", 3, 3),
    ("MAKE_READY", 5, 4),
    ("HOUSEKEEPING", 6, 5),
    ("CARPET_CLEAN", 6, 6),
    ("FINAL_WALK", 7, 7),
    ("QUALITY_CONTROL", 8, 8),
)


def _last_business_completion_date(today: date) -> date:
    """Date to match ``task.completed_date`` (Mon → Fri; Tue–Fri → prior day; weekend → Fri)."""
    wd = today.weekday()
    if wd == 0:
        return today - timedelta(days=3)
    if wd == 5:
        return today - timedelta(days=1)
    if wd == 6:
        return today - timedelta(days=2)
    return today - timedelta(days=1)


def get_yesterday_completions(
    property_id: int,
    phase_scope: list[int] | None = None,
    *,
    today: date | None = None,
) -> list[dict]:
    """Tasks completed on the last business day, for morning verification."""
    from services import scope_service

    ref = _last_business_completion_date(today or date.today())
    if phase_scope is None:
        phase_scope = scope_service.get_phase_scope(property_id)
    rows = task_repository.get_completed_on(
        property_id, ref, phase_ids=phase_scope
    )
    return [
        {
            "unit_code": r["unit_code"],
            "task_type": r["task_type"],
            "assignee": r.get("assignee"),
        }
        for r in rows
    ]


def create_task(
    property_id: int,
    turnover_id: int,
    task_type: str,
    *,
    scheduled_date: date | None = None,
    vendor_due_date: date | None = None,
    required: bool = True,
    blocking: bool = True,
    assignee: str | None = None,
    actor: str = "system",
) -> dict:
    check_writes_enabled()
    existing = task_repository.get_by_turnover(turnover_id)
    for t in existing:
        if t["task_type"] == task_type:
            raise TaskError(
                f"Task type '{task_type}' already exists for turnover {turnover_id}."
            )

    task = task_repository.insert(
        property_id,
        turnover_id,
        task_type,
        scheduled_date=scheduled_date,
        vendor_due_date=vendor_due_date,
        required=required,
        blocking=blocking,
        assignee=assignee,
    )
    audit_repository.insert(
        property_id=property_id,
        entity_type="task",
        entity_id=task["task_id"],
        field_name="created",
        old_value=None,
        new_value=task_type,
        actor=actor,
        source="task_service",
    )
    return task


def update_task(
    task_id: int,
    actor: str = "system",
    **fields,
) -> dict:
    check_writes_enabled()
    existing = task_repository.get_by_id(task_id)
    if existing is None:
        raise TaskError(f"Task {task_id} not found.")

    # When execution status becomes COMPLETED, ensure vendor_completed_at is set
    if fields.get("execution_status") == "COMPLETED" and "vendor_completed_at" not in fields:
        if existing.get("vendor_completed_at") is None:
            fields = {**fields, "vendor_completed_at": datetime.utcnow()}

    # When execution status becomes COMPLETED, stamp completed_date if empty (never overwrite)
    if (
        fields.get("execution_status") == "COMPLETED"
        and "completed_date" not in fields
        and existing.get("completed_date") is None
    ):
        fields = {**fields, "completed_date": date.today()}

    # When execution status changes from COMPLETED to any other status, clear completed_date
    if (
        existing.get("execution_status") == "COMPLETED"
        and fields.get("execution_status") is not None
        and fields.get("execution_status") != "COMPLETED"
    ):
        fields = {**fields, "completed_date": None}

    updated = task_repository.update(task_id, **fields)

    for key, new_val in fields.items():
        old_val = existing.get(key)
        if str(old_val) != str(new_val):
            audit_repository.insert(
                property_id=existing["property_id"],
                entity_type="task",
                entity_id=task_id,
                field_name=key,
                old_value=str(old_val) if old_val is not None else None,
                new_value=str(new_val) if new_val is not None else None,
                actor=actor,
                source="task_service",
            )
    return updated


def complete_task(task_id: int, actor: str = "system") -> dict:
    check_writes_enabled()
    existing = task_repository.get_by_id(task_id)
    if existing is None:
        raise TaskError(f"Task {task_id} not found.")
    if existing["execution_status"] == "COMPLETED":
        raise TaskError(f"Task {task_id} is already completed.")

    return update_task(
        task_id,
        actor=actor,
        execution_status="COMPLETED",
        vendor_completed_at=datetime.utcnow(),
    )


def has_templates_for_phase(phase_id: int) -> bool:
    """Return True if the phase has at least one active task template."""
    templates = task_repository.get_templates_by_phase(phase_id, active_only=True)
    return len(templates) > 0


def ensure_default_templates_for_phase(property_id: int, phase_id: int) -> int:
    """Idempotently insert the default pipeline templates for a phase (see 007 migration).

    Returns the count of rows inserted (0 if all types already had an active template).
    """
    check_writes_enabled()
    inserted = 0
    for task_type, offset_days, sort_order in _DEFAULT_PIPELINE_TEMPLATES:
        row = task_repository.insert_template_if_no_active_for_phase(
            property_id,
            phase_id,
            task_type,
            offset_days,
            sort_order=sort_order,
            required=True,
            blocking=True,
        )
        if row is not None:
            inserted += 1
    return inserted


def instantiate_templates(
    property_id: int,
    turnover_id: int,
    phase_id: int,
    move_out_date: date,
    actor: str = "system",
) -> list[dict]:
    templates = task_repository.get_templates_by_phase(phase_id, active_only=True)
    existing = task_repository.get_by_turnover(turnover_id)
    existing_types = {t["task_type"] for t in existing}

    created = []
    for tmpl in templates:
        if tmpl["task_type"] in existing_types:
            continue
        due = move_out_date + timedelta(days=tmpl["offset_days_from_move_out"])
        task = create_task(
            property_id,
            turnover_id,
            tmpl["task_type"],
            vendor_due_date=due,
            required=tmpl["required"],
            blocking=tmpl["blocking"],
            actor=actor,
        )
        created.append(task)
    return created


def get_schedule_rows(
    property_id: int,
    phase_scope: list[int] | None = None,
) -> list[dict]:
    """Return a flat list of schedule-ready task rows for a property.

    Each row contains: task_id, task_type, unit_code, scheduled_date,
    vendor_due_date, execution_status, assignee.
    """
    from db.repository import unit_repository

    from services import scope_service

    if phase_scope is None:
        phase_scope = scope_service.get_phase_scope(property_id)
    turnovers = turnover_repository.get_open_by_property(property_id, phase_ids=phase_scope)
    if not turnovers:
        return []

    units_by_id: dict[int, dict] = {}
    for u in unit_repository.get_by_property(
        property_id, active_only=False, phase_ids=phase_scope
    ):
        units_by_id[u["unit_id"]] = u

    rows: list[dict] = []
    for t in turnovers:
        unit = units_by_id.get(t["unit_id"])
        unit_code = unit["unit_code_norm"] if unit else "?"
        tasks = task_repository.get_by_turnover(t["turnover_id"])
        for task in tasks:
            rows.append({
                "task_id": task["task_id"],
                "task_type": task["task_type"],
                "unit_code": unit_code,
                "scheduled_date": task.get("scheduled_date"),
                "vendor_due_date": task.get("vendor_due_date"),
                "execution_status": task["execution_status"],
                "assignee": task.get("assignee"),
            })
    return rows


def get_readiness(turnover_id: int) -> dict:
    tasks = task_repository.get_by_turnover(turnover_id)
    state = readiness_domain.readiness_state(tasks)
    completed, total = readiness_domain.completion_ratio(tasks)
    blockers = readiness_domain.blocking_tasks(tasks)
    next_task = readiness_domain.next_pending_task(tasks)
    return {
        "state": state,
        "completed": completed,
        "total": total,
        "blockers": blockers,
        "next_task": next_task,
        "tasks": tasks,
    }

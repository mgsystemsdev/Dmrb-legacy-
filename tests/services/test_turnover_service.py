"""Tests for services/turnover_service.py against the JSON backend."""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from services.turnover_service import (
    PLACEHOLDER_READY_DATE_OFFSET_DAYS,
    TurnoverError,
    backfill_placeholder_ready_dates,
    cancel_turnover,
    close_turnover,
    create_turnover,
    get_turnover_detail,
    search_unit,
    update_turnover,
)

# ── Create ───────────────────────────────────────────────────────────────────


def test_create_turnover_success():
    """Unit 6 (B-203) has no open turnover and has a phase — creation should succeed with tasks."""
    fake_unit = {
        "unit_id": 6,
        "property_id": 1,
        "is_active": True,
        "phase_id": 1,
        "unit_code_norm": "B-203",
    }
    fake_turnover = {
        "turnover_id": 100,
        "property_id": 1,
        "unit_id": 6,
        "move_out_date": date(2026, 4, 1),
    }

    with (
        patch("db.repository.unit_repository.get_by_id", return_value=fake_unit),
        patch("db.repository.turnover_repository.get_open_by_unit", return_value=None),
        patch("db.repository.turnover_repository.insert", return_value=fake_turnover),
        patch("db.repository.turnover_repository.update", return_value=fake_turnover),
        patch("db.repository.audit_repository.insert"),
        patch("services.risk_service.evaluate_sla_state"),
        patch("services.risk_service.sync_risk_from_sla"),
        patch("services.task_service.instantiate_templates", return_value=[{"task_id": 1}]),
        patch("services.task_service.has_templates_for_phase", return_value=True),
        patch("services.task_service.ensure_default_templates_for_phase"),
    ):
        turnover = create_turnover(
            property_id=1,
            unit_id=6,
            move_out_date=date(2026, 4, 1),
        )
    assert turnover["unit_id"] == 6
    assert turnover["move_out_date"] == date(2026, 4, 1)


def test_create_turnover_fails_if_no_phase():
    """Unit with no phase should fail turnover creation."""
    fake_unit = {"unit_id": 7, "property_id": 1, "is_active": True, "phase_id": None}
    with (
        patch("db.repository.unit_repository.get_by_id", return_value=fake_unit),
        patch("db.repository.turnover_repository.get_open_by_unit", return_value=None),
    ):
        with pytest.raises(TurnoverError, match="has no phase assigned"):
            create_turnover(property_id=1, unit_id=7, move_out_date=date(2026, 4, 1))


def test_create_turnover_fails_if_no_templates():
    """Unit with phase but no templates should fail."""
    fake_unit = {"unit_id": 6, "property_id": 1, "is_active": True, "phase_id": 1}
    fake_turnover = {"turnover_id": 100, "property_id": 1, "unit_id": 6}
    with (
        patch("db.repository.unit_repository.get_by_id", return_value=fake_unit),
        patch("db.repository.turnover_repository.get_open_by_unit", return_value=None),
        patch("db.repository.turnover_repository.insert", return_value=fake_turnover),
        patch("db.repository.turnover_repository.update", return_value=fake_turnover),
        patch("db.repository.audit_repository.insert"),
        patch("services.task_service.has_templates_for_phase", return_value=False),
        patch("services.task_service.ensure_default_templates_for_phase"),
    ):
        with pytest.raises(TurnoverError, match="has no active task templates"):
            create_turnover(property_id=1, unit_id=6, move_out_date=date(2026, 4, 1))


def test_create_turnover_fails_if_instantiate_returns_empty():
    """If no tasks are actually created, the turnover creation should abort."""
    fake_unit = {"unit_id": 6, "property_id": 1, "is_active": True, "phase_id": 1}
    fake_turnover = {"turnover_id": 100, "property_id": 1, "unit_id": 6}
    with (
        patch("db.repository.unit_repository.get_by_id", return_value=fake_unit),
        patch("db.repository.turnover_repository.get_open_by_unit", return_value=None),
        patch("db.repository.turnover_repository.insert", return_value=fake_turnover),
        patch("db.repository.turnover_repository.update", return_value=fake_turnover),
        patch("db.repository.audit_repository.insert"),
        patch("services.task_service.has_templates_for_phase", return_value=True),
        patch("services.task_service.ensure_default_templates_for_phase"),
        patch("services.task_service.instantiate_templates", return_value=[]),
    ):
        with pytest.raises(TurnoverError, match="No tasks were generated"):
            create_turnover(property_id=1, unit_id=6, move_out_date=date(2026, 4, 1))


def test_create_turnover_sets_placeholder_ready_date():
    """New turnover gets report_ready_date = move_out_date + PLACEHOLDER_READY_DATE_OFFSET_DAYS."""
    move_out = date(2026, 4, 1)
    fake_unit = {"unit_id": 6, "property_id": 1, "is_active": True, "phase_id": 1}
    fake_turnover = {"turnover_id": 100, "property_id": 1, "unit_id": 6, "move_out_date": move_out}

    with (
        patch("db.repository.unit_repository.get_by_id", return_value=fake_unit),
        patch("db.repository.turnover_repository.get_open_by_unit", return_value=None),
        patch("db.repository.turnover_repository.insert", return_value=fake_turnover),
        patch(
            "db.repository.turnover_repository.update",
            side_effect=lambda tid, **kw: {**fake_turnover, **kw},
        ),
        patch("db.repository.audit_repository.insert"),
        patch("services.risk_service.evaluate_sla_state"),
        patch("services.risk_service.sync_risk_from_sla"),
        patch("services.task_service.instantiate_templates", return_value=[{"task_id": 1}]),
        patch("services.task_service.has_templates_for_phase", return_value=True),
        patch("services.task_service.ensure_default_templates_for_phase"),
    ):
        turnover = create_turnover(
            property_id=1,
            unit_id=6,
            move_out_date=move_out,
        )
    expected = move_out + timedelta(days=PLACEHOLDER_READY_DATE_OFFSET_DAYS)
    assert turnover["report_ready_date"] == expected


def test_create_turnover_placeholder_audit_source():
    """Placeholder ready date audit entry has source 'turnover_service.placeholder'."""
    move_out = date(2026, 4, 1)
    fake_unit = {"unit_id": 6, "property_id": 1, "is_active": True, "phase_id": 1}
    fake_turnover = {"turnover_id": 100, "property_id": 1, "unit_id": 6, "move_out_date": move_out}

    with (
        patch("db.repository.unit_repository.get_by_id", return_value=fake_unit),
        patch("db.repository.turnover_repository.get_open_by_unit", return_value=None),
        patch("db.repository.turnover_repository.insert", return_value=fake_turnover),
        patch("db.repository.turnover_repository.update", return_value=fake_turnover),
        patch("db.repository.audit_repository.insert") as mock_audit,
        patch("services.risk_service.evaluate_sla_state"),
        patch("services.risk_service.sync_risk_from_sla"),
        patch("services.task_service.instantiate_templates", return_value=[{"task_id": 1}]),
        patch("services.task_service.has_templates_for_phase", return_value=True),
        patch("services.task_service.ensure_default_templates_for_phase"),
    ):
        create_turnover(
            property_id=1,
            unit_id=6,
            move_out_date=move_out,
        )

    placeholder_audits = [
        c.kwargs
        for c in mock_audit.call_args_list
        if c.kwargs.get("source") == "turnover_service.placeholder"
        and c.kwargs.get("field_name") == "report_ready_date"
    ]
    assert len(placeholder_audits) >= 1
    expected = str(move_out + timedelta(days=PLACEHOLDER_READY_DATE_OFFSET_DAYS))
    assert placeholder_audits[0]["new_value"] == expected


def test_create_turnover_duplicate_raises():
    """Unit 1 already has an open turnover — should raise TurnoverError."""
    fake_unit = {"unit_id": 6, "property_id": 1, "is_active": True, "phase_id": 1}
    with (
        patch("db.repository.unit_repository.get_by_id", return_value=fake_unit),
        patch(
            "db.repository.turnover_repository.get_open_by_unit", return_value={"turnover_id": 123}
        ),
    ):
        with pytest.raises(TurnoverError, match="already has an open turnover"):
            create_turnover(
                property_id=1,
                unit_id=6,
                move_out_date=date(2026, 4, 1),
            )


def test_create_turnover_inactive_unit_raises():
    """An inactive unit should be rejected."""
    with patch(
        "db.repository.unit_repository.get_by_id",
        return_value={"unit_id": 6, "property_id": 1, "is_active": False},
    ):
        with pytest.raises(TurnoverError, match="inactive"):
            create_turnover(
                property_id=1,
                unit_id=6,
                move_out_date=date(2026, 4, 1),
            )


# ── Update ───────────────────────────────────────────────────────────────────


def test_update_turnover_success():
    """Updating move_in_date on an open turnover should succeed."""
    new_date = date(2026, 4, 10)
    fake_turnover = {
        "turnover_id": 1,
        "property_id": 1,
        "unit_id": 1,
        "closed_at": None,
        "canceled_at": None,
    }
    with (
        patch("db.repository.turnover_repository.get_by_id", return_value=fake_turnover),
        patch(
            "db.repository.turnover_repository.update",
            return_value={**fake_turnover, "move_in_date": new_date},
        ),
        patch("db.repository.audit_repository.insert"),
    ):
        updated = update_turnover(1, actor="test", move_in_date=new_date)
    assert updated["move_in_date"] == new_date


def test_update_closed_turnover_raises():
    """Closing a turnover then updating it should raise TurnoverError."""
    fake_turnover = {
        "turnover_id": 1,
        "property_id": 1,
        "unit_id": 1,
        "closed_at": date(2026, 4, 2),
    }
    with patch("db.repository.turnover_repository.get_by_id", return_value=fake_turnover):
        with pytest.raises(TurnoverError, match="closed or canceled"):
            update_turnover(1, actor="test", move_in_date=date(2026, 5, 1))


# ── Close / Cancel ───────────────────────────────────────────────────────────


def test_close_turnover():
    """Closing sets closed_at to a non-None value."""
    fake_turnover = {
        "turnover_id": 1,
        "property_id": 1,
        "unit_id": 1,
        "closed_at": None,
        "canceled_at": None,
    }
    with (
        patch("db.repository.turnover_repository.get_by_id", return_value=fake_turnover),
        patch(
            "services.turnover_service.update_turnover",
            return_value={**fake_turnover, "closed_at": date.today()},
        ),
    ):
        result = close_turnover(1, actor="test")
    assert result["closed_at"] is not None


def test_cancel_turnover():
    """Canceling sets canceled_at and cancel_reason."""
    fake_turnover = {
        "turnover_id": 2,
        "property_id": 1,
        "unit_id": 1,
        "closed_at": None,
        "canceled_at": None,
    }
    with (
        patch("db.repository.turnover_repository.get_by_id", return_value=fake_turnover),
        patch(
            "services.turnover_service.update_turnover",
            return_value={**fake_turnover, "canceled_at": date.today(), "cancel_reason": "test"},
        ),
    ):
        result = cancel_turnover(2, reason="test", actor="test")
    assert result["canceled_at"] is not None
    assert result["cancel_reason"] == "test"


# ── Search ───────────────────────────────────────────────────────────────────


def test_search_unit():
    """search_unit normalizes raw code and finds the unit."""
    with patch(
        "db.repository.unit_repository.get_by_code_norm",
        return_value={"unit_id": 4, "unit_code_norm": "B-201"},
    ):
        unit = search_unit(property_id=1, raw_code=" b-201 ")
    assert unit is not None
    assert unit["unit_code_norm"] == "B-201"
    assert unit["unit_id"] == 4


# ── Detail ───────────────────────────────────────────────────────────────────


def test_get_turnover_detail():
    """get_turnover_detail returns enriched dict with lifecycle_phase."""
    fake_turnover = {
        "turnover_id": 1,
        "property_id": 1,
        "unit_id": 1,
        "move_out_date": date(2026, 4, 1),
        "move_in_date": date(2026, 4, 15),
        "closed_at": None,
        "canceled_at": None,
    }
    with patch("db.repository.turnover_repository.get_by_id", return_value=fake_turnover):
        detail = get_turnover_detail(1)
    assert detail is not None
    assert "lifecycle_phase" in detail
    assert "days_since_move_out" in detail
    assert "days_to_move_in" in detail
    assert "vacancy_days" in detail


# ── Backfill placeholder ready dates ─────────────────────────────────────────


def test_backfill_placeholder_ready_dates_fills_null():
    """Turnovers with NULL report_ready_date and no manual override get placeholder."""
    fake_turnovers = [
        {
            "turnover_id": 30,
            "property_id": 1,
            "unit_id": 1,
            "move_out_date": date(2026, 3, 10),
            "report_ready_date": None,
            "ready_manual_override_at": None,
        },
    ]
    mock_update = patch(
        "services.turnover_service.turnover_repository.update",
        return_value={**fake_turnovers[0], "report_ready_date": date(2026, 3, 20)},
    )
    mock_audit = patch("services.turnover_service.audit_repository.insert")
    with (
        patch(
            "services.turnover_service.turnover_repository.get_open_by_property",
            return_value=fake_turnovers,
        ),
        mock_update as m_update,
        mock_audit as m_audit,
    ):
        result = backfill_placeholder_ready_dates(1)

    assert result["filled"] == 1
    assert result["skipped"] == 0
    expected_date = date(2026, 3, 10) + timedelta(days=PLACEHOLDER_READY_DATE_OFFSET_DAYS)
    m_update.assert_called_once_with(30, report_ready_date=expected_date)
    m_audit.assert_called_once()
    assert m_audit.call_args.kwargs["source"] == "turnover_service.placeholder"
    assert m_audit.call_args.kwargs["field_name"] == "report_ready_date"


def test_backfill_placeholder_skips_existing_ready_date():
    """Turnovers that already have report_ready_date are skipped."""
    fake_turnovers = [
        {
            "turnover_id": 31,
            "property_id": 1,
            "unit_id": 2,
            "move_out_date": date(2026, 3, 5),
            "report_ready_date": date(2026, 3, 25),
            "ready_manual_override_at": None,
        },
    ]
    with patch(
        "services.turnover_service.turnover_repository.get_open_by_property",
        return_value=fake_turnovers,
    ):
        result = backfill_placeholder_ready_dates(1)

    assert result["filled"] == 0
    assert result["skipped"] == 1


def test_backfill_placeholder_skips_manual_override():
    """Turnovers where ready_manual_override_at is set are skipped even if report_ready_date is NULL."""
    from datetime import datetime, timezone

    fake_turnovers = [
        {
            "turnover_id": 32,
            "property_id": 1,
            "unit_id": 3,
            "move_out_date": date(2026, 3, 8),
            "report_ready_date": None,
            "ready_manual_override_at": datetime(2026, 3, 9, tzinfo=timezone.utc),
        },
    ]
    with patch(
        "services.turnover_service.turnover_repository.get_open_by_property",
        return_value=fake_turnovers,
    ):
        result = backfill_placeholder_ready_dates(1)

    assert result["filled"] == 0
    assert result["skipped"] == 1


def test_backfill_placeholder_mixed():
    """Mix of fillable and skippable turnovers produces correct counts."""
    fake_turnovers = [
        {
            "turnover_id": 40,
            "property_id": 1,
            "unit_id": 1,
            "move_out_date": date(2026, 3, 1),
            "report_ready_date": None,
            "ready_manual_override_at": None,
        },
        {
            "turnover_id": 41,
            "property_id": 1,
            "unit_id": 2,
            "move_out_date": date(2026, 3, 2),
            "report_ready_date": date(2026, 3, 20),
            "ready_manual_override_at": None,
        },
        {
            "turnover_id": 42,
            "property_id": 1,
            "unit_id": 3,
            "move_out_date": date(2026, 3, 3),
            "report_ready_date": None,
            "ready_manual_override_at": None,
        },
    ]
    mock_update = patch(
        "services.turnover_service.turnover_repository.update",
        side_effect=lambda tid, **kw: {
            **[t for t in fake_turnovers if t["turnover_id"] == tid][0],
            **kw,
        },
    )
    mock_audit = patch("services.turnover_service.audit_repository.insert")
    with (
        patch(
            "services.turnover_service.turnover_repository.get_open_by_property",
            return_value=fake_turnovers,
        ),
        mock_update as m_update,
        mock_audit,
    ):
        result = backfill_placeholder_ready_dates(1)

    assert result["filled"] == 2
    assert result["skipped"] == 1
    assert m_update.call_count == 2

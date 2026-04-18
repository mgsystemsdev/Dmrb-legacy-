"""Tests for services/turnover_service.py against the JSON backend."""
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from services.turnover_service import (
    PLACEHOLDER_READY_DATE_OFFSET_DAYS,
    TurnoverError,
    backfill_placeholder_ready_dates,
    backfill_tasks_all_properties,
    backfill_tasks_for_property,
    create_turnover,
    update_turnover,
    close_turnover,
    cancel_turnover,
    search_unit,
    get_turnover_detail,
)


# ── Create ───────────────────────────────────────────────────────────────────


def test_create_turnover_success():
    """Unit 6 (B-203) has no open turnover — creation should succeed."""
    turnover = create_turnover(
        property_id=1,
        unit_id=6,
        move_out_date=date(2026, 4, 1),
    )
    assert turnover["unit_id"] == 6
    assert turnover["turnover_id"] == 6  # next counter value
    assert turnover["move_out_date"] == date(2026, 4, 1)
    assert turnover["closed_at"] is None
    assert turnover["canceled_at"] is None


def test_create_turnover_sets_placeholder_ready_date():
    """New turnover gets report_ready_date = move_out_date + PLACEHOLDER_READY_DATE_OFFSET_DAYS."""
    move_out = date(2026, 4, 1)
    turnover = create_turnover(
        property_id=1,
        unit_id=6,
        move_out_date=move_out,
    )
    expected = move_out + timedelta(days=PLACEHOLDER_READY_DATE_OFFSET_DAYS)
    assert turnover["report_ready_date"] == expected


def test_create_turnover_placeholder_audit_source():
    """Placeholder ready date audit entry has source 'turnover_service.placeholder'."""
    from db.repository import audit_repository

    move_out = date(2026, 4, 1)
    turnover = create_turnover(
        property_id=1,
        unit_id=6,
        move_out_date=move_out,
    )
    tid = turnover["turnover_id"]
    audits = audit_repository.get_by_entity("turnover", tid)
    placeholder_audits = [
        a for a in audits
        if a.get("source") == "turnover_service.placeholder"
        and a.get("field_name") == "report_ready_date"
    ]
    assert len(placeholder_audits) >= 1
    expected = str(move_out + timedelta(days=PLACEHOLDER_READY_DATE_OFFSET_DAYS))
    assert placeholder_audits[0]["new_value"] == expected


def test_create_turnover_duplicate_raises():
    """Unit 1 already has an open turnover — should raise TurnoverError."""
    with pytest.raises(TurnoverError, match="already has an open turnover"):
        create_turnover(
            property_id=1,
            unit_id=1,
            move_out_date=date(2026, 4, 1),
        )


def test_create_turnover_inactive_unit_raises():
    """An inactive unit should be rejected."""
    from db.repository import unit_repository

    # Set unit 6 to inactive
    unit_repository.update(6, is_active=False)

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
    updated = update_turnover(1, actor="test", move_in_date=new_date)
    assert updated["move_in_date"] == new_date


def test_update_closed_turnover_raises():
    """Closing a turnover then updating it should raise TurnoverError."""
    close_turnover(1, actor="test")

    with pytest.raises(TurnoverError, match="closed or canceled"):
        update_turnover(1, actor="test", move_in_date=date(2026, 5, 1))


# ── Close / Cancel ───────────────────────────────────────────────────────────


def test_close_turnover():
    """Closing sets closed_at to a non-None value."""
    result = close_turnover(1, actor="test")
    assert result["closed_at"] is not None


def test_cancel_turnover():
    """Canceling sets canceled_at and cancel_reason."""
    result = cancel_turnover(2, reason="Lease fell through", actor="test")
    assert result["canceled_at"] is not None
    assert result["cancel_reason"] == "Lease fell through"


# ── Search ───────────────────────────────────────────────────────────────────


def test_search_unit():
    """search_unit normalizes raw code and finds the unit."""
    unit = search_unit(property_id=1, raw_code=" b-201 ")
    assert unit is not None
    assert unit["unit_code_norm"] == "B-201"
    assert unit["unit_id"] == 4


# ── Detail ───────────────────────────────────────────────────────────────────


def test_get_turnover_detail():
    """get_turnover_detail returns enriched dict with lifecycle_phase."""
    detail = get_turnover_detail(1)
    assert detail is not None
    assert "lifecycle_phase" in detail
    assert "days_since_move_out" in detail
    assert "days_to_move_in" in detail
    assert "vacancy_days" in detail


# ── Backfill (Layer 3) ───────────────────────────────────────────────────────


def test_backfill_tasks_for_property_repairs_and_skips():
    """backfill_tasks_for_property calls ensure_turnover_has_tasks per open turnover; counts repaired vs skipped."""
    fake_turnovers = [
        {"turnover_id": 10, "property_id": 1, "unit_id": 1},
        {"turnover_id": 11, "property_id": 1, "unit_id": 2},
    ]
    with patch(
        "services.turnover_service.turnover_repository.get_open_by_property",
        return_value=fake_turnovers,
    ), patch(
        "services.turnover_service.ensure_turnover_has_tasks",
        side_effect=[True, False],
    ):
        result = backfill_tasks_for_property(1)
    assert result["repaired"] == 1
    assert result["skipped"] == 1
    assert result["errors"] == []


def test_backfill_tasks_all_properties_aggregates():
    """backfill_tasks_all_properties runs per-property backfill and aggregates totals and by_property."""
    with patch(
        "services.turnover_service.property_repository.get_all",
        return_value=[{"property_id": 1}, {"property_id": 2}],
    ), patch(
        "services.turnover_service.backfill_tasks_for_property",
        side_effect=[
            {"repaired": 2, "skipped": 3, "errors": []},
            {"repaired": 1, "skipped": 0, "errors": []},
        ],
    ):
        result = backfill_tasks_all_properties()
    assert result["total_repaired"] == 3
    assert result["total_skipped"] == 3
    assert result["by_property"] == {
        1: {"repaired": 2, "skipped": 3, "errors": []},
        2: {"repaired": 1, "skipped": 0, "errors": []},
    }
    assert result["errors"] == []


def test_backfill_tasks_for_property_continues_on_error():
    """When ensure_turnover_has_tasks raises for one turnover, error is recorded and rest still processed."""
    fake_turnovers = [
        {"turnover_id": 20, "property_id": 1, "unit_id": 1},
        {"turnover_id": 21, "property_id": 1, "unit_id": 2},
    ]
    with patch(
        "services.turnover_service.turnover_repository.get_open_by_property",
        return_value=fake_turnovers,
    ), patch(
        "services.turnover_service.ensure_turnover_has_tasks",
        side_effect=[TurnoverError("Turnover 20 not found"), True],
    ):
        result = backfill_tasks_for_property(1)
    assert result["repaired"] == 1
    assert result["skipped"] == 0
    assert len(result["errors"]) == 1
    assert "turnover_id=20" in result["errors"][0]
    assert "Turnover 20 not found" in result["errors"][0]


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
    with patch(
        "services.turnover_service.turnover_repository.get_open_by_property",
        return_value=fake_turnovers,
    ), mock_update as m_update, mock_audit as m_audit:
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
        side_effect=lambda tid, **kw: {**[t for t in fake_turnovers if t["turnover_id"] == tid][0], **kw},
    )
    mock_audit = patch("services.turnover_service.audit_repository.insert")
    with patch(
        "services.turnover_service.turnover_repository.get_open_by_property",
        return_value=fake_turnovers,
    ), mock_update as m_update, mock_audit:
        result = backfill_placeholder_ready_dates(1)

    assert result["filled"] == 2
    assert result["skipped"] == 1
    assert m_update.call_count == 2

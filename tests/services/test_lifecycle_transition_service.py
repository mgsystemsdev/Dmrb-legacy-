"""Tests for services.lifecycle_transition_service."""

from datetime import date, datetime
from unittest.mock import patch

import pytest

from domain import turnover_lifecycle
from domain.availability_status import MANUAL_READY_ON_NOTICE
from services.lifecycle_transition_service import transition_turnover_phase
from services.turnover_service import TurnoverError


def _open_turnover(**overrides):
    row = {
        "turnover_id": 1,
        "property_id": 100,
        "unit_id": 5,
        "move_out_date": date(2099, 6, 1),
        "move_in_date": None,
        "canceled_at": None,
        "closed_at": None,
        "cancel_reason": None,
        "manual_ready_status": None,
        "manual_ready_confirmed_at": None,
        "availability_status": None,
        "available_date": None,
        "legal_confirmed_at": None,
        "legal_confirmation_source": None,
    }
    row.update(overrides)
    return row


@patch("services.lifecycle_transition_service.check_writes_enabled")
@patch("services.lifecycle_transition_service.lifecycle_event_repository.insert")
@patch("services.lifecycle_transition_service.update_turnover")
@patch("services.lifecycle_transition_service.turnover_repository.get_by_id")
def test_property_mismatch_raises(mock_get, mock_upd, mock_ins, _cw):
    mock_get.return_value = _open_turnover(property_id=999)
    with pytest.raises(TurnoverError, match="does not belong"):
        transition_turnover_phase(
            100,
            1,
            turnover_lifecycle.PHASE_ON_NOTICE,
            actor="test",
            source="test",
            today=date(2026, 1, 15),
        )
    mock_upd.assert_not_called()
    mock_ins.assert_not_called()


@patch("services.lifecycle_transition_service.check_writes_enabled")
@patch("services.lifecycle_transition_service.lifecycle_event_repository.insert")
@patch("services.lifecycle_transition_service.update_turnover")
@patch("services.lifecycle_transition_service.turnover_repository.get_by_id")
def test_cancel_requires_reason(mock_get, mock_upd, mock_ins, _cw):
    mock_get.return_value = _open_turnover()
    with pytest.raises(TurnoverError, match="cancel_reason"):
        transition_turnover_phase(
            100,
            1,
            turnover_lifecycle.PHASE_CANCELED,
            actor="test",
            source="test",
            today=date(2026, 1, 15),
            cancel_reason=None,
        )
    mock_upd.assert_not_called()


@patch("services.lifecycle_transition_service.check_writes_enabled")
@patch("services.lifecycle_transition_service.lifecycle_event_repository.insert")
@patch("services.lifecycle_transition_service.turnover_repository.get_by_id")
def test_closed_to_on_notice_transition_error(mock_get, mock_ins, _cw):
    mock_get.return_value = _open_turnover(closed_at=datetime(2026, 1, 1))
    with pytest.raises(turnover_lifecycle.TransitionError, match="not allowed"):
        transition_turnover_phase(
            100,
            1,
            turnover_lifecycle.PHASE_ON_NOTICE,
            actor="test",
            source="test",
            today=date(2026, 1, 15),
        )
    mock_ins.assert_not_called()


@patch("services.lifecycle_transition_service.check_writes_enabled")
@patch("services.lifecycle_transition_service.lifecycle_event_repository.insert")
@patch("services.lifecycle_transition_service.update_turnover")
@patch("services.lifecycle_transition_service.turnover_repository.get_by_id")
def test_idempotent_same_phase_no_insert(mock_get, mock_upd, mock_ins, _cw):
    row = _open_turnover(
        manual_ready_status=MANUAL_READY_ON_NOTICE,
        availability_status="on notice",
    )
    mock_get.return_value = row
    out = transition_turnover_phase(
        100,
        1,
        turnover_lifecycle.PHASE_ON_NOTICE,
        actor="test",
        source="test",
        today=date(2026, 1, 15),
    )
    assert out is row
    mock_upd.assert_not_called()
    mock_ins.assert_not_called()


@patch("services.lifecycle_transition_service.check_writes_enabled")
@patch("services.lifecycle_transition_service.lifecycle_event_repository.insert")
@patch("services.lifecycle_transition_service.update_turnover")
@patch("services.lifecycle_transition_service.turnover_repository.get_by_id")
def test_pre_notice_to_on_notice_records_event(mock_get, mock_upd, mock_ins, _cw):
    before = _open_turnover()
    after = {
        **before,
        "manual_ready_status": MANUAL_READY_ON_NOTICE,
        "availability_status": "on notice",
    }

    mock_get.side_effect = [before, after]

    def upd(tid, **kw):
        assert tid == 1
        assert kw.get("manual_ready_status") == MANUAL_READY_ON_NOTICE
        return after

    mock_upd.side_effect = upd

    result = transition_turnover_phase(
        100,
        1,
        turnover_lifecycle.PHASE_ON_NOTICE,
        actor="op",
        source="unit_test",
        today=date(2026, 1, 15),
    )
    assert turnover_lifecycle.lifecycle_phase(result, date(2026, 1, 15)) == (
        turnover_lifecycle.PHASE_ON_NOTICE
    )
    mock_ins.assert_called_once()
    call_kw = mock_ins.call_args
    assert call_kw[0][:4] == (100, 1, turnover_lifecycle.PHASE_ON_NOTICE, "op")
    assert call_kw[0][4] == "unit_test"
    assert call_kw[1]["from_phase"] == turnover_lifecycle.PHASE_PRE_NOTICE

"""Tests for services/lifecycle_automation_service — run_available_date_transition and Phase 5 automation."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch, ANY

import pytest

from services.automation.lifecycle_automation_service import (
    AUTO_TRANSITION_MAX_DV,
    AUTOMATION_SOURCE,
    run_available_date_transition,
    run_available_date_transition_all_properties,
    run_on_notice_turnover_creation,
    run_on_notice_turnover_creation_all_properties,
    run_midnight_automation,
)


# Fixed date for deterministic tests.
TODAY = date(2026, 3, 20)


# ── Scenario A: Eligible unit (DV=0, move-out day) ───────────────────────────


def test_scenario_a_eligible_unit_transitions_and_audits():
    """On Notice, move_out_date=today (DV=0) → status transitions with override lock, tasks ensured, audit written."""
    fake_turnovers = [
        {
            "turnover_id": 99,
            "property_id": 1,
            "unit_id": 10,
            "manual_ready_status": "On Notice",
            "move_out_date": TODAY,
            "closed_at": None,
            "canceled_at": None,
        }
    ]
    with (
        patch("services.automation.lifecycle_automation_service.turnover_repository.get_open_by_property", return_value=fake_turnovers),
        patch("services.automation.lifecycle_automation_service.turnover_service.update_turnover") as mock_update,
        patch("services.automation.lifecycle_automation_service.turnover_service.ensure_turnover_has_tasks") as mock_ensure,
        patch("services.automation.lifecycle_automation_service.audit_repository.insert") as mock_audit,
    ):
        result = run_available_date_transition(property_id=1, today=TODAY)

    assert result["transitioned"] == 1
    assert result["errors"] == []
    mock_update.assert_called_once_with(
        99,
        actor="system",
        manual_ready_status="Vacant Not Ready",
        availability_status="vacant not ready",
        status_manual_override_at=ANY,
    )
    mock_ensure.assert_called_once_with(99, actor="system")
    audit_calls = [c for c in mock_audit.call_args_list if c.kwargs.get("source") == AUTOMATION_SOURCE]
    assert len(audit_calls) == 1
    assert audit_calls[0].kwargs["entity_type"] == "turnover"
    assert audit_calls[0].kwargs["entity_id"] == 99
    assert "On Notice" in (audit_calls[0].kwargs.get("new_value") or "")


# ── Scenario A2: Eligible unit (DV=5, catch-up window) ───────────────────────


def test_scenario_a2_catchup_dv5_transitions():
    """On Notice, move_out_date 5 days ago (DV=5) → still within catch-up window, transitions."""
    fake_turnovers = [
        {
            "turnover_id": 100,
            "property_id": 1,
            "unit_id": 11,
            "manual_ready_status": "On Notice",
            "move_out_date": TODAY - timedelta(days=5),
            "closed_at": None,
            "canceled_at": None,
        }
    ]
    with (
        patch("services.automation.lifecycle_automation_service.turnover_repository.get_open_by_property", return_value=fake_turnovers),
        patch("services.automation.lifecycle_automation_service.turnover_service.update_turnover") as mock_update,
        patch("services.automation.lifecycle_automation_service.turnover_service.ensure_turnover_has_tasks"),
        patch("services.automation.lifecycle_automation_service.audit_repository.insert"),
    ):
        result = run_available_date_transition(property_id=1, today=TODAY)

    assert result["transitioned"] == 1
    mock_update.assert_called_once()


# ── Scenario A3: DV beyond catch-up window ───────────────────────────────────


def test_scenario_a3_beyond_catchup_window_no_change():
    """On Notice, move_out_date 11+ days ago (DV > AUTO_TRANSITION_MAX_DV) → no transition."""
    fake_turnovers = [
        {
            "turnover_id": 101,
            "property_id": 1,
            "unit_id": 12,
            "manual_ready_status": "On Notice",
            "move_out_date": TODAY - timedelta(days=AUTO_TRANSITION_MAX_DV + 1),
            "closed_at": None,
            "canceled_at": None,
        }
    ]
    with (
        patch("services.automation.lifecycle_automation_service.turnover_repository.get_open_by_property", return_value=fake_turnovers),
        patch("services.automation.lifecycle_automation_service.turnover_service.update_turnover") as mock_update,
    ):
        result = run_available_date_transition(property_id=1, today=TODAY)

    assert result["transitioned"] == 0
    mock_update.assert_not_called()


# ── Scenario B: Future move-out date ─────────────────────────────────────────


def test_scenario_b_future_move_out_no_change():
    """On Notice, move_out_date > today → no transition."""
    fake_turnovers = [
        {
            "turnover_id": 98,
            "property_id": 1,
            "unit_id": 9,
            "manual_ready_status": "On Notice",
            "move_out_date": date(2026, 4, 1),
            "closed_at": None,
            "canceled_at": None,
        }
    ]
    with (
        patch("services.automation.lifecycle_automation_service.turnover_repository.get_open_by_property", return_value=fake_turnovers),
        patch("services.automation.lifecycle_automation_service.turnover_service.update_turnover") as mock_update,
        patch("services.automation.lifecycle_automation_service.audit_repository.insert") as mock_audit,
    ):
        result = run_available_date_transition(property_id=1, today=TODAY)

    assert result["transitioned"] == 0
    assert result["errors"] == []
    mock_update.assert_not_called()
    automation_audits = [c for c in mock_audit.call_args_list if c.kwargs.get("source") == AUTOMATION_SOURCE]
    assert len(automation_audits) == 0


# ── Scenario C: Turnover already Vacant Not Ready (no duplicate) ─────────────


def test_scenario_c_already_vacant_not_ready_not_selected():
    """Turnover already Vacant Not Ready → not in eligible list."""
    fake_turnovers = [
        {
            "turnover_id": 97,
            "property_id": 1,
            "manual_ready_status": "Vacant Not Ready",
            "move_out_date": TODAY,
            "closed_at": None,
            "canceled_at": None,
        }
    ]
    with (
        patch("services.automation.lifecycle_automation_service.turnover_repository.get_open_by_property", return_value=fake_turnovers),
        patch("services.automation.lifecycle_automation_service.turnover_service.update_turnover") as mock_update,
    ):
        result = run_available_date_transition(property_id=1, today=TODAY)

    assert result["transitioned"] == 0
    mock_update.assert_not_called()


# ── Scenario D: Not On Notice (Vacant Ready / None) ─────────────────────────


def test_scenario_d_not_on_notice_no_change():
    """manual_ready_status Vacant Ready or None → no transition."""
    fake_turnovers = [
        {"turnover_id": 96, "property_id": 1, "manual_ready_status": "Vacant Ready", "move_out_date": TODAY, "closed_at": None, "canceled_at": None},
        {"turnover_id": 95, "property_id": 1, "manual_ready_status": None, "move_out_date": TODAY, "closed_at": None, "canceled_at": None},
    ]
    with (
        patch("services.automation.lifecycle_automation_service.turnover_repository.get_open_by_property", return_value=fake_turnovers),
        patch("services.automation.lifecycle_automation_service.turnover_service.update_turnover") as mock_update,
    ):
        result = run_available_date_transition(property_id=1, today=TODAY)

    assert result["transitioned"] == 0
    mock_update.assert_not_called()


# ── Scenario E: Repeat execution (idempotent) ─────────────────────────────────


def test_scenario_e_repeat_execution_no_duplicate():
    """After first run turnover is Vacant Not Ready; second run does not select it (idempotent)."""
    fake_first = [
        {"turnover_id": 94, "property_id": 1, "manual_ready_status": "On Notice", "move_out_date": TODAY, "closed_at": None, "canceled_at": None}
    ]
    with (
        patch("services.automation.lifecycle_automation_service.turnover_repository.get_open_by_property", return_value=fake_first),
        patch("services.automation.lifecycle_automation_service.turnover_service.update_turnover"),
        patch("services.automation.lifecycle_automation_service.turnover_service.ensure_turnover_has_tasks"),
        patch("services.automation.lifecycle_automation_service.audit_repository.insert"),
    ):
        r1 = run_available_date_transition(property_id=1, today=TODAY)
    assert r1["transitioned"] == 1

    fake_second = [
        {"turnover_id": 94, "property_id": 1, "manual_ready_status": "Vacant Not Ready", "move_out_date": TODAY, "closed_at": None, "canceled_at": None}
    ]
    with (
        patch("services.automation.lifecycle_automation_service.turnover_repository.get_open_by_property", return_value=fake_second),
        patch("services.automation.lifecycle_automation_service.turnover_service.update_turnover") as mock_update,
    ):
        r2 = run_available_date_transition(property_id=1, today=TODAY)

    assert r2["transitioned"] == 0
    mock_update.assert_not_called()


# ── Eligibility: move_out_date None ──────────────────────────────────────────


def test_eligible_requires_move_out_date():
    """Turnover with manual_ready_status On Notice but move_out_date None is not eligible."""
    fake_turnovers = [
        {"turnover_id": 93, "property_id": 1, "manual_ready_status": "On Notice", "move_out_date": None, "closed_at": None, "canceled_at": None}
    ]
    with (
        patch("services.automation.lifecycle_automation_service.turnover_repository.get_open_by_property", return_value=fake_turnovers),
        patch("services.automation.lifecycle_automation_service.turnover_service.update_turnover") as mock_update,
    ):
        result = run_available_date_transition(property_id=1, today=TODAY)

    assert result["transitioned"] == 0
    mock_update.assert_not_called()


# ── all_properties ───────────────────────────────────────────────────────────


def test_run_all_properties_aggregates():
    """run_available_date_transition_all_properties returns aggregated counts and by_property."""
    with (
        patch("db.repository.property_repository.get_all") as mock_get_all,
        patch("services.automation.lifecycle_automation_service.run_available_date_transition") as mock_run,
    ):
        mock_get_all.return_value = [{"property_id": 1}, {"property_id": 2}]
        mock_run.side_effect = [{"transitioned": 2, "errors": []}, {"transitioned": 0, "errors": ["err"]}]
        result = run_available_date_transition_all_properties(today=TODAY)
    assert result["total_transitioned"] == 2
    assert result["by_property"] == {1: {"transitioned": 2, "errors": []}, 2: {"transitioned": 0, "errors": ["err"]}}
    assert "property_id=2" in result["errors"][0]


# ── Phase 5: On Notice snapshot → create turnover ─────────────────────────────


def test_on_notice_creation_creates_turnover_and_deletes_snapshot():
    """Snapshot row with available_date <= today and no turnover → create turnover, ensure tasks, delete snapshot."""
    snapshot_rows = [
        {
            "property_id": 1,
            "unit_id": 101,
            "available_date": TODAY,
            "move_in_ready_date": date(2026, 3, 25),
        }
    ]
    with (
        patch(
            "services.automation.lifecycle_automation_service.unit_on_notice_snapshot_repository.get_eligible_for_automation",
            return_value=snapshot_rows,
        ),
        patch(
            "services.automation.lifecycle_automation_service.turnover_repository.get_open_by_unit",
            return_value=None,
        ),
        patch(
            "services.automation.lifecycle_automation_service.turnover_service.create_turnover",
            return_value={"turnover_id": 200, "unit_id": 101, "property_id": 1},
        ) as mock_create,
        patch(
            "services.automation.lifecycle_automation_service.turnover_service.update_turnover",
        ) as mock_update,
        patch(
            "services.automation.lifecycle_automation_service.turnover_service.ensure_turnover_has_tasks",
        ) as mock_ensure,
        patch(
            "services.automation.lifecycle_automation_service.audit_repository.insert",
        ) as mock_audit,
        patch(
            "services.automation.lifecycle_automation_service.unit_on_notice_snapshot_repository.delete_by_unit",
        ) as mock_delete,
    ):
        result = run_on_notice_turnover_creation(property_id=1, today=TODAY)

    assert result["created"] == 1
    assert result["errors"] == []
    mock_create.assert_called_once_with(
        property_id=1,
        unit_id=101,
        move_out_date=TODAY,
        actor="system",
    )
    mock_update.assert_called_once()
    assert mock_update.call_args.kwargs["availability_status"] == "vacant not ready"
    assert mock_update.call_args.kwargs["manual_ready_status"] == "Vacant Not Ready"
    assert mock_update.call_args.kwargs["report_ready_date"] == date(2026, 3, 25)
    mock_ensure.assert_called_once_with(200, actor="system")
    mock_delete.assert_called_once_with(1, 101)
    audit_calls = [c for c in mock_audit.call_args_list if c.kwargs.get("source") == AUTOMATION_SOURCE]
    assert len(audit_calls) == 1


def test_on_notice_creation_skips_unit_with_open_turnover():
    """Snapshot row for unit that already has open turnover → skip (no create)."""
    snapshot_rows = [
        {"property_id": 1, "unit_id": 102, "available_date": TODAY, "move_in_ready_date": None}
    ]
    with (
        patch(
            "services.automation.lifecycle_automation_service.unit_on_notice_snapshot_repository.get_eligible_for_automation",
            return_value=snapshot_rows,
        ),
        patch(
            "services.automation.lifecycle_automation_service.turnover_repository.get_open_by_unit",
            return_value={"turnover_id": 99},
        ),
        patch(
            "services.automation.lifecycle_automation_service.turnover_service.create_turnover",
        ) as mock_create,
    ):
        result = run_on_notice_turnover_creation(property_id=1, today=TODAY)

    assert result["created"] == 0
    assert result["errors"] == []
    mock_create.assert_not_called()


def test_run_midnight_automation_aggregates():
    """run_midnight_automation runs both transitions and on_notice_creation and returns combined result."""
    with (
        patch(
            "services.automation.lifecycle_automation_service.run_available_date_transition_all_properties",
            return_value={
                "total_transitioned": 1,
                "by_property": {1: {"transitioned": 1, "errors": []}},
                "errors": [],
            },
        ) as mock_trans,
        patch(
            "services.automation.lifecycle_automation_service.run_on_notice_turnover_creation_all_properties",
            return_value={
                "total_created": 2,
                "by_property": {1: {"created": 2, "errors": []}},
                "errors": [],
            },
        ) as mock_cre,
    ):
        result = run_midnight_automation(today=TODAY)

    assert result["today"] == TODAY.isoformat()
    assert result["transitions"]["total_transitioned"] == 1
    assert result["on_notice_created"]["total_created"] == 2
    assert result["errors"] == []
    mock_trans.assert_called_once_with(today=TODAY)
    mock_cre.assert_called_once_with(today=TODAY)

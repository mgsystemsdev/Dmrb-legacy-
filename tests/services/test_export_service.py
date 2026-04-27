"""Tests for Weekly Summary export (board-backed, no extra DB queries in export layer)."""

from datetime import date, timedelta
from unittest.mock import patch

from domain import turnover_lifecycle as tl
from domain.readiness import IN_PROGRESS, READY
from services.exports import export_service

TODAY = date(2026, 3, 20)


def _board_item(
    *,
    tid: int,
    unit_code: str = "101A",
    phase: str = tl.PHASE_VACANT_NOT_READY,
    vacancy_days: int | None = 15,
    days_since_move_out: int | None = 8,
    move_in_date: date | None = None,
    report_ready_date: date | None = None,
    readiness_state: str = READY,
    agreements: dict | None = None,
    priority: str = "NORMAL",
    has_wd: bool = False,
    blockers: list | None = None,
) -> dict:
    ag = agreements or {
        "inspection": "GREEN",
        "sla": "GREEN",
        "move_in": "GREEN",
        "plan": "GREEN",
        "viol": "GREEN",
    }
    return {
        "turnover": {
            "turnover_id": tid,
            "lifecycle_phase": phase,
            "vacancy_days": vacancy_days,
            "days_since_move_out": days_since_move_out,
            "move_in_date": move_in_date,
            "report_ready_date": report_ready_date,
        },
        "unit": {
            "unit_code_norm": unit_code,
            "has_wd_expected": has_wd,
            "phase_id": 1,
        },
        "tasks": [],
        "readiness": {
            "state": readiness_state,
            "completed": 0,
            "total": 1,
            "blockers": blockers or [],
        },
        "sla": {
            "risk_level": "OK",
            "days_until_breach": None,
            "move_in_pressure": None,
        },
        "priority": priority,
        "agreements": ag,
        "_sort_key": (0, tid),
    }


REQUIRED_SECTIONS = (
    export_service.SECTION_KEY_METRICS,
    export_service.SECTION_ALERTS,
    export_service.SECTION_UPCOMING_MOVE_INS,
    export_service.SECTION_UPCOMING_READY,
    export_service.SECTION_WD_NOT_INSTALLED,
    export_service.SECTION_AGING,
)


def test_weekly_summary_empty_board_has_all_sections():
    with (
        patch("services.exports.export_service.board_service.get_board", return_value=[]),
        patch("services.exports.export_service.scope_service.get_phase_scope", return_value=[]),
    ):
        text = export_service.build_weekly_summary_text(1, today=TODAY, phase_scope=[])
    assert text.strip()
    for title in REQUIRED_SECTIONS:
        assert title in text
    assert "Total Active: 0" in text
    for b in export_service.AGING_BUCKETS:
        assert f"{b}:" in text


def test_weekly_summary_populated_board_metrics_and_alerts():
    board = [
        _board_item(
            tid=1,
            unit_code="A1",
            agreements={
                "inspection": "GREEN",
                "sla": "RED",
                "move_in": "RED",
                "plan": "RED",
                "viol": "RED",
            },
            move_in_date=TODAY + timedelta(days=2),
            report_ready_date=TODAY + timedelta(days=4),
            has_wd=True,
            vacancy_days=25,
        ),
        _board_item(
            tid=2,
            unit_code="B2",
            phase=tl.PHASE_ON_NOTICE,
            vacancy_days=None,
            days_since_move_out=8,
            readiness_state=IN_PROGRESS,
        ),
    ]

    with (
        patch("services.exports.export_service.board_service.get_board", return_value=board),
        patch("services.exports.export_service.scope_service.get_phase_scope", return_value=[]),
    ):
        text = export_service.build_weekly_summary_text(99, today=TODAY, phase_scope=[])

    for title in REQUIRED_SECTIONS:
        assert title in text
    assert "Total Active: 2" in text
    assert "Vacant: 1" in text
    assert "On Notice: 1" in text
    assert "SLA Breaches" in text
    assert "  - A1" in text
    assert "Move-In Risk" in text
    assert "Stalled Tasks" in text
    assert "  - B2" in text
    assert "Plan Breaches" in text
    assert "Upcoming Move-Ins" in text
    assert "A1" in text and "move-in" in text
    assert "Upcoming Ready" in text
    assert "W/D Not Installed" in text
    assert "  - A1" in text
    assert "21-30: 1" in text or "21-30:" in text


def test_weekly_summary_bytes_non_empty():
    with (
        patch("services.exports.export_service.board_service.get_board", return_value=[]),
        patch("services.exports.export_service.scope_service.get_phase_scope", return_value=[]),
    ):
        raw = export_service.build_weekly_summary_bytes(1, today=TODAY, phase_scope=[])
    assert len(raw) > 0
    assert raw.decode("utf-8").startswith("DMRB Weekly Summary")


def test_is_finite_numeric():
    assert not export_service.is_finite_numeric(None)
    assert not export_service.is_finite_numeric(float("nan"))
    assert export_service.is_finite_numeric(7)
    assert export_service.is_finite_numeric(7.0)


def test_weekly_summary_aging_skips_nan_vacancy_days():
    board = [
        _board_item(tid=1, vacancy_days=float("nan")),
        _board_item(tid=2, vacancy_days=5, unit_code="B1"),
    ]
    with (
        patch("services.exports.export_service.board_service.get_board", return_value=board),
        patch("services.exports.export_service.scope_service.get_phase_scope", return_value=[]),
    ):
        text = export_service.build_weekly_summary_text(1, today=TODAY, phase_scope=[], board=board)
    assert "  1-10: 1" in text

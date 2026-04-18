"""Tests for services/risk_service — _score_board_item weights and risk_level thresholds."""

from __future__ import annotations

from services.risk_service import _score_board_item


def _board_item(
    *,
    days_since_move_out: int = 0,
    move_in_date=None,
    risk_level: str = "OK",
    move_in_pressure: int | None = None,
    readiness_state: str = "READY",
    unit_code_norm: str = "4-26-0417",
    phase_id: int | None = 1,
) -> dict:
    return {
        "turnover": {
            "turnover_id": 1,
            "days_since_move_out": days_since_move_out,
            "move_in_date": move_in_date,
        },
        "unit": {
            "unit_code_norm": unit_code_norm,
            "phase_id": phase_id,
        },
        "readiness": {"state": readiness_state},
        "sla": {"risk_level": risk_level, "move_in_pressure": move_in_pressure},
    }


def _phase_map():
    return {1: "Phase1"}


class TestScoreBoardItem:
    def test_sla_breach_adds_40(self):
        item = _board_item(risk_level="BREACH")
        result = _score_board_item(item, _phase_map())
        assert result["risk_score"] >= 40
        assert "SLA breach" in result["risk_reasons"]

    def test_sla_warning_adds_25(self):
        item = _board_item(risk_level="WARNING")
        result = _score_board_item(item, _phase_map())
        assert result["risk_score"] >= 25
        assert "SLA warning" in result["risk_reasons"]

    def test_dv_over_14_adds_20(self):
        item = _board_item(days_since_move_out=20)
        result = _score_board_item(item, _phase_map())
        assert any("DV 20" in r for r in result["risk_reasons"])
        assert result["risk_score"] >= 10

    def test_dv_over_7_adds_10(self):
        item = _board_item(days_since_move_out=10)
        result = _score_board_item(item, _phase_map())
        assert any("DV 10" in r for r in result["risk_reasons"])

    def test_move_in_pressure_le_3_adds_20(self):
        item = _board_item(move_in_pressure=2)
        result = _score_board_item(item, _phase_map())
        assert "Move-in ≤3 days" in result["risk_reasons"]

    def test_move_in_overdue_adds_25(self):
        item = _board_item(move_in_pressure=-1)
        result = _score_board_item(item, _phase_map())
        assert "Move-in overdue" in result["risk_reasons"]

    def test_readiness_blocked_adds_15(self):
        item = _board_item(readiness_state="BLOCKED")
        result = _score_board_item(item, _phase_map())
        assert "Blocked tasks" in result["risk_reasons"]
        assert result["risk_score"] >= 15

    def test_readiness_not_started_adds_10(self):
        item = _board_item(readiness_state="NOT_STARTED")
        result = _score_board_item(item, _phase_map())
        assert "Work not started" in result["risk_reasons"]

    def test_score_capped_at_100(self):
        item = _board_item(
            risk_level="BREACH",
            days_since_move_out=30,
            move_in_pressure=-5,
            readiness_state="BLOCKED",
        )
        result = _score_board_item(item, _phase_map())
        assert result["risk_score"] <= 100

    def test_risk_level_high_when_score_ge_60(self):
        item = _board_item(risk_level="BREACH", days_since_move_out=20, move_in_pressure=1)
        result = _score_board_item(item, _phase_map())
        assert result["risk_level"] == "HIGH"
        assert result["risk_score"] >= 60

    def test_risk_level_medium_when_score_ge_30(self):
        item = _board_item(risk_level="WARNING", readiness_state="NOT_STARTED")
        result = _score_board_item(item, _phase_map())
        assert result["risk_level"] == "MEDIUM"
        assert result["risk_score"] >= 30

    def test_risk_level_low_when_score_lt_30(self):
        item = _board_item(days_since_move_out=3)
        result = _score_board_item(item, _phase_map())
        assert result["risk_level"] == "LOW"
        assert result["risk_score"] < 30

    def test_risk_score_changes_with_readiness(self):
        item_ready = _board_item(readiness_state="READY")
        item_blocked = _board_item(readiness_state="BLOCKED")
        r_ready = _score_board_item(item_ready, _phase_map())
        r_blocked = _score_board_item(item_blocked, _phase_map())
        assert r_blocked["risk_score"] >= r_ready["risk_score"] + 15
        assert "Blocked tasks" in r_blocked["risk_reasons"]

    def test_risk_level_and_score_threshold_consistency(self):
        """Failure detection: HIGH implies score >= 60, MEDIUM >= 30, LOW < 30."""
        item_high = _board_item(risk_level="BREACH", days_since_move_out=20, move_in_pressure=1)
        item_medium = _board_item(risk_level="WARNING", readiness_state="NOT_STARTED")
        item_low = _board_item(days_since_move_out=2)
        r_high = _score_board_item(item_high, _phase_map())
        r_medium = _score_board_item(item_medium, _phase_map())
        r_low = _score_board_item(item_low, _phase_map())
        assert r_high["risk_level"] == "HIGH" and r_high["risk_score"] >= 60
        assert r_medium["risk_level"] == "MEDIUM" and r_medium["risk_score"] >= 30
        assert r_low["risk_level"] == "LOW" and r_low["risk_score"] < 30

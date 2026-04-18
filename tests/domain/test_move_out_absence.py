"""Tests for domain.move_out_absence — should_cancel_turnover rule."""

from __future__ import annotations

from domain.move_out_absence import should_cancel_turnover


class TestShouldCancelTurnover:
    def test_count_below_threshold_returns_false(self):
        assert should_cancel_turnover(0, threshold=2) is False
        assert should_cancel_turnover(1, threshold=2) is False

    def test_count_at_or_above_threshold_returns_true(self):
        assert should_cancel_turnover(2, threshold=2) is True
        assert should_cancel_turnover(3, threshold=2) is True

    def test_custom_threshold(self):
        assert should_cancel_turnover(1, threshold=3) is False
        assert should_cancel_turnover(3, threshold=3) is True

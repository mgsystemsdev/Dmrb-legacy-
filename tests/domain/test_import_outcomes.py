"""Tests for domain.import_outcomes — classify_row_outcome."""

from __future__ import annotations

from domain.import_outcomes import (
    CONFLICT,
    INVALID,
    OK,
    SKIPPED_OVERRIDE,
    classify_row_outcome,
)


class TestClassifyRowOutcome:
    def test_override_skipped_returns_skipped_override(self):
        status, reason = classify_row_outcome(override_skipped=True)
        assert status == SKIPPED_OVERRIDE
        assert reason is not None

    def test_has_required_fields_false_returns_invalid(self):
        status, _ = classify_row_outcome(has_required_fields=False)
        assert status == INVALID

    def test_has_open_turnover_false_returns_conflict(self):
        status, _ = classify_row_outcome(has_open_turnover=False, has_required_fields=True)
        assert status == CONFLICT

    def test_ok_when_all_conditions_met(self):
        status, reason = classify_row_outcome(
            has_open_turnover=True,
            has_required_fields=True,
            override_skipped=False,
        )
        assert status == OK
        assert reason is None

"""Tests for domain.manual_override — should_apply_import_value."""

from __future__ import annotations

from datetime import datetime

from domain.manual_override import should_apply_import_value


class TestShouldApplyImportValue:
    def test_no_override_apply_accept(self):
        apply_val, clear_override = should_apply_import_value(
            current_value="2025-01-15",
            override_timestamp=None,
            incoming_value="2025-01-20",
        )
        assert apply_val is True
        assert clear_override is False

    def test_override_and_incoming_matches_current_apply_and_clear(self):
        apply_val, clear_override = should_apply_import_value(
            current_value="2025-01-15",
            override_timestamp=datetime(2025, 1, 10),
            incoming_value="2025-01-15",
        )
        assert apply_val is True
        assert clear_override is True

    def test_override_and_incoming_differs_do_not_apply(self):
        apply_val, clear_override = should_apply_import_value(
            current_value="2025-01-15",
            override_timestamp=datetime(2025, 1, 10),
            incoming_value="2025-01-20",
        )
        assert apply_val is False
        assert clear_override is False

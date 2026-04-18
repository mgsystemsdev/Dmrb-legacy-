"""Tests for domain.availability_status — status_allows_turnover_creation, status_is_vacant, status_is_on_notice, availability_status_to_manual_ready_status."""

from __future__ import annotations

from domain.availability_status import (
    availability_status_to_manual_ready_status,
    status_allows_turnover_creation,
    status_is_on_notice,
    status_is_vacant,
)


class TestStatusAllowsTurnoverCreation:
    def test_vacant_ready_allows(self):
        assert status_allows_turnover_creation("vacant ready") is True
        assert status_allows_turnover_creation("Vacant Ready") is True

    def test_vacant_not_ready_allows(self):
        assert status_allows_turnover_creation("vacant not ready") is True
        assert status_allows_turnover_creation("Vacant Not Ready") is True

    def test_other_status_disallows(self):
        assert status_allows_turnover_creation("occupied") is False
        assert status_allows_turnover_creation("") is False

    def test_case_insensitive(self):
        assert status_allows_turnover_creation("  VACANT READY  ") is True


class TestStatusIsVacant:
    def test_vacant_ready_is_vacant(self):
        assert status_is_vacant("vacant ready") is True

    def test_vacant_not_ready_is_vacant(self):
        assert status_is_vacant("vacant not ready") is True

    def test_other_not_vacant(self):
        assert status_is_vacant("occupied") is False
        assert status_is_vacant(None) is False


class TestStatusIsOnNotice:
    def test_on_notice(self):
        assert status_is_on_notice("on notice") is True
        assert status_is_on_notice("On Notice") is True

    def test_on_notice_break(self):
        assert status_is_on_notice("on notice (break)") is True

    def test_other_not_on_notice(self):
        assert status_is_on_notice("vacant not ready") is False
        assert status_is_on_notice(None) is False


class TestAvailabilityStatusToManualReadyStatus:
    def test_on_notice_maps(self):
        assert availability_status_to_manual_ready_status("on notice") == "On Notice"
        assert availability_status_to_manual_ready_status("on notice (break)") == "On Notice"

    def test_vacant_maps(self):
        assert availability_status_to_manual_ready_status("vacant not ready") == "Vacant Not Ready"
        assert availability_status_to_manual_ready_status("vacant ready") == "Vacant Ready"

    def test_beacon_maps(self):
        assert availability_status_to_manual_ready_status("beacon not ready") == "Vacant Not Ready"
        assert availability_status_to_manual_ready_status("beacon ready") == "Vacant Ready"

    def test_unknown_returns_none(self):
        assert availability_status_to_manual_ready_status("occupied") is None
        assert availability_status_to_manual_ready_status(None) is None
        assert availability_status_to_manual_ready_status("") is None

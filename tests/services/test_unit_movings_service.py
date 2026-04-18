"""Tests for unit_movings_service — lookup key normalization."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from services.unit_movings_service import (
    get_latest_movings_lookup,
    normalize_moving_unit_key,
)


def test_normalize_moving_unit_key_strips_unit_prefix():
    assert normalize_moving_unit_key("Unit 4-26-0417") == "4-26-0417"


def test_normalize_moving_unit_key_collapses_whitespace():
    assert normalize_moving_unit_key("  4-26-0417  ") == "4-26-0417"


def test_get_latest_movings_lookup_merges_duplicate_normalized_keys():
    """Legacy rows with different spellings map to one key; latest date wins."""
    raw = {
        "Unit 4-26-0417": date(2025, 1, 1),
        "4-26-0417": date(2025, 6, 1),
    }
    with patch(
        "services.unit_movings_service.unit_movings_repository.get_latest_movings_by_unit",
        return_value=raw,
    ):
        m = get_latest_movings_lookup()
    assert len(m) == 1
    assert m["4-26-0417"] == date(2025, 6, 1)

"""Tests for domain.unit_identity — normalize_unit_code, parse_unit_parts, compose_identity_key."""

from __future__ import annotations

from domain.unit_identity import (
    compose_identity_key,
    normalize_unit_code,
    parse_unit_parts,
)


class TestNormalizeUnitCode:
    def test_strips_and_uppercases(self):
        assert normalize_unit_code("  4-26-0417  ") == "4-26-0417"

    def test_removes_leading_unit_prefix(self):
        assert normalize_unit_code("  unit  4-26-0417  ") == "4-26-0417"
        assert normalize_unit_code("Unit 4-26-0417") == "4-26-0417"

    def test_collapses_internal_whitespace(self):
        assert normalize_unit_code("4  \t  26  0417") == "4 26 0417"


class TestParseUnitParts:
    def test_parses_phase_building_unit(self):
        result = parse_unit_parts("4-26-0417")
        assert result["phase_code"] == "4"
        assert result["building_code"] == "26"
        assert result["unit_number"] == "0417"

    def test_no_match_returns_full_as_unit_number(self):
        result = parse_unit_parts("SINGLE")
        assert result["phase_code"] is None
        assert result["building_code"] is None
        assert result["unit_number"] == "SINGLE"


class TestComposeIdentityKey:
    def test_compose_identity_key(self):
        assert compose_identity_key(1, "4-26-0417") == "1:4-26-0417"

"""Unit tests for ``unit_master_import_plan`` (no DB: repositories mocked)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pandas as pd
import pytest

from services.unit_master_import_plan import build_unit_master_import_report, normalize_unit_master_report


@pytest.fixture
def empty_structure():
    with patch("services.unit_master_import_plan.property_repository") as pr, patch(
        "services.unit_master_import_plan.unit_repository"
    ) as ur:
        pr.get_phases.return_value = []
        pr.get_buildings.return_value = []
        ur.get_by_code_norm.return_value = None
        yield pr, ur


def test_empty_unit_and_duplicate_error(empty_structure):
    _pr, ur = empty_structure
    ur.get_by_code_norm.return_value = None
    df = pd.DataFrame(
        {
            "unit_code": ["A", "", "A"],
        }
    )
    r = build_unit_master_import_report(1, df, strict=False)
    assert r["total_rows"] == 3
    assert r["error_rows"] == 2  # empty + duplicate
    assert r["rows"][0]["status"] == "valid"
    assert r["rows"][1]["status"] == "error"
    assert r["rows"][2]["status"] == "error"


def test_strict_blocks_new_unit(empty_structure):
    _pr, ur = empty_structure
    ur.get_by_code_norm.return_value = None
    df = pd.DataFrame({"unit_code": ["X"]})
    r = build_unit_master_import_report(1, df, strict=True)
    assert r["error_rows"] == 1
    assert r["has_blocking_errors"] is True
    assert "strict" in r["rows"][0]["messages"][0].lower()


def test_skips_existing_unit_no_gross_warning(empty_structure):
    """Same as import: existing rows are skipped before reading gross_sq_ft."""
    _pr, ur = empty_structure
    ur.get_by_code_norm.side_effect = lambda _p, n: ({"unit_id": 1} if n == "A" else None)
    df = pd.DataFrame(
        {
            "unit_code": ["A"],
            "Gross Sq. Ft.": ["not_a_number"],
        }
    )
    r = build_unit_master_import_report(1, df, strict=False)
    assert r["rows"][0]["status"] == "valid"
    assert r["rows"][0]["messages"] == []


def test_would_create_phase_and_unit(empty_structure):
    _pr, ur = empty_structure
    ur.get_by_code_norm.return_value = None
    df = pd.DataFrame(
        {
            "unit_code": ["101"],
            "phase": ["P1"],
        }
    )
    r = build_unit_master_import_report(1, df, strict=False)
    assert r["error_rows"] == 0
    parsed = [json.loads(s) for s in r["rows"][0]["actions"]]
    types = [a["type"] for a in parsed]
    assert "would_create_phase" in types
    assert "would_create_unit" in types


def test_valid_row_has_empty_messages(empty_structure):
    _pr, ur = empty_structure
    ur.get_by_code_norm.return_value = None
    df = pd.DataFrame({"unit_code": ["Z"]})
    r = build_unit_master_import_report(1, df, strict=False)
    assert r["rows"][0]["status"] == "valid"
    assert r["rows"][0]["messages"] == []


def test_header_only_zero_rows(empty_structure):
    _pr, ur = empty_structure
    df = pd.DataFrame(columns=["unit_code", "phase"])
    r = build_unit_master_import_report(1, df, strict=False)
    assert r["total_rows"] == 0
    assert any("header" in m.lower() for m in r["file_messages"])


def test_normalize_derives_counts():
    raw = {
        "rows": [
            {"row_index": 0, "unit_code": "A", "status": "valid", "messages": [], "actions": []},
            {"row_index": 1, "unit_code": "B", "status": "warning", "messages": ["w"], "actions": []},
        ],
        "file_messages": [],
    }
    out = normalize_unit_master_report(raw)
    assert out["valid_rows"] == 1
    assert out["warning_rows"] == 1
    assert out["error_rows"] == 0
    assert out["total_rows"] == 2


def test_gross_sq_ft_warning_does_not_block(empty_structure):
    _pr, ur = empty_structure
    ur.get_by_code_norm.return_value = None
    df = pd.DataFrame(
        {
            "unit_code": ["B"],
            "Gross Sq. Ft.": ["x"],
        }
    )
    r = build_unit_master_import_report(1, df, strict=False)
    assert r["rows"][0]["status"] == "warning"
    assert r["error_rows"] == 0
    assert r["has_blocking_errors"] is False

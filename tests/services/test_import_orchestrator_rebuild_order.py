"""Import orchestrator rebuild-order preflight (PENDING_MOVE_INS)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from db.repository import turnover_repository as turnover_repo_module
from services.imports import orchestrator


def _minimal_pending_move_ins_csv(path) -> None:
    """CSV that passes schema (5 skip rows, then header + one row)."""
    lines = ["skip"] * 5 + ["Unit,Move In Date", "1A-101,01/15/2025"]
    path.write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture
def pending_move_ins_file(tmp_path):
    p = tmp_path / "pending_move_ins.csv"
    _minimal_pending_move_ins_csv(p)
    return p


def test_strict_import_rebuild_order_blocks_when_no_open_turnovers(
    pending_move_ins_file,
    monkeypatch,
):
    monkeypatch.setattr(
        turnover_repo_module,
        "count_open_turnovers",
        lambda _pid: 0,
    )
    monkeypatch.setattr(
        orchestrator,
        "is_truthy_setting",
        lambda key: key == "STRICT_IMPORT_REBUILD_ORDER",
    )

    result = orchestrator.import_report_file(
        "PENDING_MOVE_INS",
        str(pending_move_ins_file),
        property_id=1,
    )

    assert result["status"] == "FAILED"
    assert result["batch_id"] is None
    assert any("rebuild_order_warning" in d for d in result["diagnostics"])


def test_preflight_warning_prepended_on_success_when_no_open_turnovers(
    pending_move_ins_file,
    monkeypatch,
):
    monkeypatch.setattr(
        turnover_repo_module,
        "count_open_turnovers",
        lambda _pid: 0,
    )
    monkeypatch.setattr(orchestrator, "is_truthy_setting", lambda _key: False)

    tx_cm = MagicMock()
    tx_cm.__enter__ = MagicMock(return_value=None)
    tx_cm.__exit__ = MagicMock(return_value=False)

    with patch("services.imports.orchestrator.transaction", return_value=tx_cm):
        with (
            patch.object(
                orchestrator.import_service,
                "start_batch",
                return_value={"batch_id": 99},
            ),
            patch.object(
                orchestrator.import_service,
                "mark_processing",
            ),
            patch.object(
                orchestrator.import_service,
                "complete_batch",
            ),
            patch.object(
                orchestrator.move_ins_service,
                "apply",
                return_value={"applied": 0, "conflict": 1, "invalid": 0},
            ),
        ):
            result = orchestrator.import_report_file(
                "PENDING_MOVE_INS",
                str(pending_move_ins_file),
                property_id=1,
            )

    assert result["status"] == "SUCCESS"
    assert result["diagnostics"], "expected preflight warning in diagnostics"
    assert "rebuild_order_warning" in result["diagnostics"][0]


def test_no_preflight_when_open_turnovers_exist(pending_move_ins_file, monkeypatch):
    monkeypatch.setattr(
        turnover_repo_module,
        "count_open_turnovers",
        lambda _pid: 3,
    )
    monkeypatch.setattr(orchestrator, "is_truthy_setting", lambda _key: False)

    tx_cm = MagicMock()
    tx_cm.__enter__ = MagicMock(return_value=None)
    tx_cm.__exit__ = MagicMock(return_value=False)

    with patch("services.imports.orchestrator.transaction", return_value=tx_cm):
        with (
            patch.object(
                orchestrator.import_service,
                "start_batch",
                return_value={"batch_id": 100},
            ),
            patch.object(
                orchestrator.import_service,
                "mark_processing",
            ),
            patch.object(
                orchestrator.import_service,
                "complete_batch",
            ),
            patch.object(
                orchestrator.move_ins_service,
                "apply",
                return_value={"applied": 1, "conflict": 0, "invalid": 0},
            ),
        ):
            result = orchestrator.import_report_file(
                "PENDING_MOVE_INS",
                str(pending_move_ins_file),
                property_id=1,
            )

    assert result["status"] == "SUCCESS"
    assert not any("rebuild_order_warning" in d for d in result["diagnostics"])

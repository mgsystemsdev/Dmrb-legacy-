"""Phase 5: Available Units import — On Notice with no turnover → IGNORED + snapshot (no turnover created)."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from domain import import_outcomes
from services.imports.available_units_service import apply


def test_on_notice_no_turnover_ignored_and_snapshot_upserted():
    """When status is On Notice, no open turnover, and available_date set: IGNORED and snapshot upserted, no turnover created."""
    rows = [
        {
            "Unit": "4-26-0230",
            "Status": "On notice",
            "Available Date": "03/12/2026",
            "Move-In Ready Date": "03/26/2026",
        }
    ]
    fake_unit = {"unit_id": 42, "property_id": 1, "unit_code_norm": "4-26-0230"}

    with (
        patch(
            "services.imports.available_units_service._resolve_or_create_unit",
            return_value=fake_unit,
        ),
        patch(
            "services.imports.available_units_service.turnover_repository.get_open_by_unit",
            return_value=None,
        ),
        patch(
            "services.imports.available_units_service.unit_on_notice_snapshot_repository.upsert",
        ) as mock_upsert,
        patch(
            "services.imports.available_units_service.turnover_service.create_turnover",
        ) as mock_create,
        patch(
            "services.imports.available_units_service.common.write_import_row",
        ) as mock_write,
    ):
        result = apply(batch_id=1, rows=rows, property_id=1)

    assert result["applied"] == 0
    assert result["conflict"] == 1
    mock_upsert.assert_called_once()
    call = mock_upsert.call_args
    assert call.kwargs["property_id"] == 1
    assert call.kwargs["unit_id"] == 42
    assert call.kwargs["available_date"] == date(2026, 3, 12)
    assert call.kwargs["move_in_ready_date"] == date(2026, 3, 26)
    mock_create.assert_not_called()
    mock_write.assert_called_once()
    assert mock_write.call_args.kwargs["status"] == import_outcomes.IGNORED
    assert mock_write.call_args.kwargs["reason"] == import_outcomes.ON_NOTICE_PENDING_AVAILABLE_DATE

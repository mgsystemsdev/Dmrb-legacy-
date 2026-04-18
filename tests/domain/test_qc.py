"""Tests for QC label logic (ui/helpers/formatting.qc_label).

QC Done when all required+blocking tasks are COMPLETED; otherwise QC Not Done.
"""

from __future__ import annotations

from ui.helpers.formatting import qc_label


def _task(execution_status="NOT_STARTED", required=True, blocking=True, **kw):
    return {
        "task_id": 1,
        "task_type": "PAINT",
        "execution_status": execution_status,
        "required": required,
        "blocking": blocking,
        **kw,
    }


class TestQcLabel:
    def test_all_required_blocking_completed_returns_qc_done(self):
        tasks = [
            _task(execution_status="COMPLETED"),
            _task(task_type="CLEAN", execution_status="COMPLETED"),
        ]
        assert qc_label(tasks) == "QC Done"

    def test_one_required_blocking_not_completed_returns_qc_not_done(self):
        tasks = [
            _task(execution_status="COMPLETED"),
            _task(task_type="CLEAN", execution_status="NOT_STARTED"),
        ]
        assert qc_label(tasks) == "QC Not Done"

    def test_no_required_blocking_returns_qc_done(self):
        tasks = [
            _task(required=True, blocking=False, execution_status="NOT_STARTED"),
        ]
        assert qc_label(tasks) == "QC Done"

    def test_non_required_incomplete_but_blocking_done_returns_qc_done(self):
        tasks = [
            _task(execution_status="COMPLETED"),
            _task(task_type="OPTIONAL", required=False, blocking=False, execution_status="NOT_STARTED"),
        ]
        assert qc_label(tasks) == "QC Done"

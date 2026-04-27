"""Import pipeline orchestrator.

Main entry point for processing report CSV files.  Coordinates:
checksum → validation → parse → delegate → result.

No business logic — only orchestration flow.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime

import pandas as pd

from config.settings import is_truthy_setting
from db.connection import transaction
from db.repository import turnover_repository
from domain.unit_identity import normalize_unit_code, parse_unit_parts
from services import import_service
from services.imports import (
    available_units_service,
    move_ins_service,
    move_outs_service,
    pending_fas_service,
)
from services.imports.validation.file_validator import validate_import_file
from services.imports.validation.schema_validator import (
    SKIPROWS,
    SchemaValidationError,
    validate_import_schema,
)

logger = logging.getLogger(__name__)


# ── Report type routing ──────────────────────────────────────────────────────

_REPORT_SERVICES = {
    "MOVE_OUTS": move_outs_service,
    "PENDING_MOVE_INS": move_ins_service,
    "AVAILABLE_UNITS": available_units_service,
    "PENDING_FAS": pending_fas_service,
}

# Phases whose units are processed.  Placeholder — inject from config later.
VALID_PHASES: set[str] | None = None  # None = accept all phases


# ── Public API ───────────────────────────────────────────────────────────────


def import_report_file(
    report_type: str,
    file_path: str,
    property_id: int,
) -> dict:
    """Run the full import pipeline for a single report file.

    Returns a result dictionary with status, counters, and diagnostics.
    """
    diagnostics: list[str] = []

    # ── 1. Compute checksum ──────────────────────────────────────────────
    file_bytes = _read_file_bytes(file_path)
    checksum = _compute_checksum(report_type, file_bytes)

    # ── 2. Duplicate detection (read-only; no batch created) ─────────────
    # Key is (property_id, report_type, checksum). COMPLETED → NO_OP.
    # FAILED or PROCESSING (stale crash) → allow re-run.
    # AVAILABLE_UNITS always re-runs: reconciliation may need to apply
    # readiness dates to turnovers created by other reports since the
    # last import of this same file.
    if report_type != "AVAILABLE_UNITS":
        existing = import_service.get_existing_batch(property_id, report_type, checksum)
        if existing is not None and existing["status"] == "COMPLETED":
            return _no_op_result(report_type, checksum)

    # ── 3. File validation ───────────────────────────────────────────────
    validate_import_file(file_path)

    # ── 4. Schema validation ─────────────────────────────────────────────
    try:
        validate_import_schema(report_type, file_path)
    except SchemaValidationError as exc:
        diagnostics.append(str(exc))
        return _failed_result(report_type, checksum, diagnostics)

    # ── 5. Parse CSV rows ────────────────────────────────────────────────
    rows = _parse_csv(report_type, file_path)

    # ── 6. Phase filter ──────────────────────────────────────────────────
    rows = _filter_by_phase(rows)

    if not rows:
        diagnostics.append("No rows remaining after phase filter.")
        return _failed_result(report_type, checksum, diagnostics)

    preflight_warnings: list[str] = []
    if report_type == "PENDING_MOVE_INS":
        open_n = turnover_repository.count_open_turnovers(property_id)
        if open_n == 0:
            warn = (
                "rebuild_order_warning: PENDING_MOVE_INS with zero open turnovers for "
                "this property; run MOVE_OUTS or qualifying AVAILABLE_UNITS first."
            )
            logger.warning(
                "import_rebuild_order_warning property_id=%s report_type=%s open_turnovers=0",
                property_id,
                report_type,
            )
            if is_truthy_setting("STRICT_IMPORT_REBUILD_ORDER"):
                diagnostics.append(warn)
                return _failed_result(report_type, checksum, diagnostics)
            preflight_warnings.append(warn)

    # ── 7. Route to report-specific service ──────────────────────────────
    service = _REPORT_SERVICES.get(report_type)
    if service is None:
        diagnostics.append(f"No handler for report type: {report_type}")
        return _failed_result(report_type, checksum, diagnostics)

    # ── 8-10. Atomic write: batch + rows + turnover updates all commit
    #         together, or roll back entirely on any failure.
    #         On rollback the DB is left clean — no orphaned batch or
    #         partial rows — and the same file can be re-imported.
    try:
        with transaction():
            batch = import_service.start_batch(
                property_id,
                report_type,
                file_bytes,
                checksum=checksum,
            )
            batch_id = batch["batch_id"]
            import_service.mark_processing(batch_id)

            counters = service.apply(
                batch_id=batch_id,
                rows=rows,
                property_id=property_id,
            )

            import_service.complete_batch(batch_id, record_count=len(rows))
    except Exception as exc:
        logger.exception("Import apply failed for %s", report_type)
        diagnostics.append(f"Apply error: {exc}")
        return _failed_result(report_type, checksum, diagnostics)

    return {
        "report_type": report_type,
        "checksum": checksum,
        "status": "SUCCESS",
        "batch_id": batch_id,
        "record_count": len(rows),
        "applied_count": counters.get("applied", 0),
        "conflict_count": counters.get("conflict", 0),
        "invalid_count": counters.get("invalid", 0),
        "diagnostics": preflight_warnings + diagnostics,
    }


# ── Internal helpers ─────────────────────────────────────────────────────────


def _read_file_bytes(file_path: str) -> bytes:
    with open(file_path, "rb") as f:
        return f.read()


def _compute_checksum(report_type: str, file_bytes: bytes) -> str:
    """Checksum = SHA-256 of report_type + file bytes.

    For AVAILABLE_UNITS the checksum is salted with a timestamp so the
    same file can be re-imported (readiness reconciliation may need to
    run again after other reports create turnovers).
    """
    h = hashlib.sha256()
    h.update(report_type.encode())
    h.update(file_bytes)
    if report_type == "AVAILABLE_UNITS":
        h.update(datetime.utcnow().isoformat().encode())
    return h.hexdigest()


def _parse_csv(report_type: str, file_path: str) -> list[dict]:
    """Read the CSV with appropriate skiprows and return a list of row dicts."""
    skiprows = SKIPROWS.get(report_type, 0)

    df = pd.read_csv(file_path, skiprows=skiprows, index_col=False)

    # Pending FAS uses "Unit Number" in the raw file
    if report_type == "PENDING_FAS" and "Unit Number" in df.columns:
        df = df.rename(columns={"Unit Number": "Unit"})

    return df.to_dict(orient="records")


def _filter_by_phase(rows: list[dict]) -> list[dict]:
    """Keep only rows whose unit phase is in ``VALID_PHASES``.

    When ``VALID_PHASES`` is ``None`` all rows pass through (placeholder).
    """
    if VALID_PHASES is None:
        return rows

    filtered = []
    for row in rows:
        unit_raw = str(row.get("Unit", ""))
        unit_norm = normalize_unit_code(unit_raw)
        parts = parse_unit_parts(unit_norm)
        phase = parts.get("phase_code")
        if phase is None or phase in VALID_PHASES:
            filtered.append(row)
    return filtered


def _no_op_result(report_type: str, checksum: str) -> dict:
    return {
        "report_type": report_type,
        "checksum": checksum,
        "status": "NO_OP",
        "batch_id": None,
        "record_count": 0,
        "applied_count": 0,
        "conflict_count": 0,
        "invalid_count": 0,
        "diagnostics": ["Duplicate file — already imported."],
    }


def _failed_result(
    report_type: str,
    checksum: str,
    diagnostics: list[str],
    *,
    batch_id: int | None = None,
) -> dict:
    return {
        "report_type": report_type,
        "checksum": checksum,
        "status": "FAILED",
        "batch_id": batch_id,
        "record_count": 0,
        "applied_count": 0,
        "conflict_count": 0,
        "invalid_count": 0,
        "diagnostics": diagnostics,
    }

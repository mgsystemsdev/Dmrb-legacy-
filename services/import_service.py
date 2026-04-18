"""Import service — coordinates file import, validation, and batch tracking.

Enforces invariants:
  - Duplicate file detection via checksum.
  - Row-level validation status tracking.
  - Batch status lifecycle (PENDING → PROCESSING → COMPLETED / FAILED).
"""

from __future__ import annotations

import hashlib
import io

import pandas as pd

from db.repository import import_repository
from services.write_guard import check_writes_enabled


class ImportError(Exception):
    pass


def compute_checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def get_existing_batch(property_id: int, report_type: str, checksum: str) -> dict | None:
    """Read-only: return the latest batch for (property_id, report_type, checksum), or None."""
    return import_repository.get_batch_by_checksum(property_id, checksum, report_type)


def start_batch(
    property_id: int,
    report_type: str,
    file_content: bytes,
    checksum: str | None = None,
) -> dict:
    """Create a PENDING batch. Duplicate key is (property_id, report_type, checksum).
    COMPLETED → raise ImportError (reject). FAILED or PROCESSING (stale) → allow re-run."""
    check_writes_enabled()
    if checksum is None:
        checksum = compute_checksum(file_content)

    existing = import_repository.get_batch_by_checksum(property_id, checksum, report_type)
    if existing is not None and existing["status"] == "COMPLETED":
        raise ImportError(
            f"File already imported (batch {existing['batch_id']}, "
            f"status: {existing['status']})."
        )

    batch = import_repository.insert_batch(
        property_id=property_id,
        report_type=report_type,
        checksum=checksum,
        status="PENDING",
    )
    return batch


def record_row(
    property_id: int,
    batch_id: int,
    raw_json: dict,
    validation_status: str,
    *,
    unit_code_raw: str | None = None,
    unit_code_norm: str | None = None,
    move_out_date=None,
    move_in_date=None,
    conflict_flag: bool = False,
    conflict_reason: str | None = None,
) -> dict:
    check_writes_enabled()
    return import_repository.insert_row(
        property_id=property_id,
        batch_id=batch_id,
        validation_status=validation_status,
        raw_json=raw_json,
        unit_code_raw=unit_code_raw,
        unit_code_norm=unit_code_norm,
        move_out_date=move_out_date,
        move_in_date=move_in_date,
        conflict_flag=conflict_flag,
        conflict_reason=conflict_reason,
    )


def complete_batch(batch_id: int, record_count: int) -> dict:
    check_writes_enabled()
    return import_repository.update_batch_status(
        batch_id, "COMPLETED", record_count=record_count,
    )


def fail_batch(batch_id: int) -> dict:
    check_writes_enabled()
    return import_repository.update_batch_status(batch_id, "FAILED")


def mark_processing(batch_id: int) -> dict:
    check_writes_enabled()
    return import_repository.update_batch_status(batch_id, "PROCESSING")


def get_batch_detail(batch_id: int) -> dict | None:
    batch = import_repository.get_batch_by_id(batch_id)
    if batch is None:
        return None
    rows = import_repository.get_rows_by_batch(batch_id)
    ok = sum(1 for r in rows if r["validation_status"] == "OK")
    invalid = sum(1 for r in rows if r["validation_status"] == "INVALID")
    conflicts = sum(1 for r in rows if r["conflict_flag"])
    batch["rows"] = rows
    batch["summary"] = {
        "total": len(rows),
        "ok": ok,
        "invalid": invalid,
        "conflicts": conflicts,
    }
    return batch


def get_history(property_id: int, limit: int = 50) -> list[dict]:
    return import_repository.get_batches_by_property(property_id, limit=limit)


def preview_file(file_content: bytes, filename: str, max_rows: int = 20) -> pd.DataFrame:
    """Parse an uploaded file and return the first *max_rows* rows as a DataFrame.

    For CSVs with junk/header rows before the real data, scans for the first
    line with multiple comma-separated fields and uses it as the header.
    """
    try:
        if filename.endswith(".xlsx"):
            return pd.read_excel(io.BytesIO(file_content), nrows=max_rows)
        return _read_csv_flexible(file_content, max_rows=max_rows)
    except Exception as exc:
        raise ImportError(f"Unable to parse file: {exc}") from exc


def _read_csv_flexible(raw_bytes: bytes, *, max_rows: int | None = None) -> pd.DataFrame:
    """Parse a CSV that may have junk/header rows before the real data."""
    try:
        return pd.read_csv(io.BytesIO(raw_bytes), nrows=max_rows)
    except Exception:
        pass

    lines = raw_bytes.decode("utf-8", errors="replace").splitlines()
    header_idx = 0
    for i, line in enumerate(lines):
        if line.count(",") >= 1:
            header_idx = i
            break

    return pd.read_csv(io.BytesIO(raw_bytes), skiprows=header_idx, nrows=max_rows)


def validate_dataframe(df: pd.DataFrame) -> list[str]:
    """Run basic validation checks on a preview DataFrame.

    Returns a list of error strings (empty means valid).
    """
    errors: list[str] = []
    if df.empty:
        errors.append("File contains no data rows.")
    if df.columns.duplicated().any():
        errors.append("Duplicate column names detected.")
    null_pct = df.isnull().mean()
    for col in null_pct[null_pct > 0.5].index:
        errors.append(f"Column '{col}' is more than 50% empty.")
    return errors


def get_missing_move_outs(property_id: int) -> list[dict]:
    """Return import rows with move-in but no move-out (PENDING_MOVE_INS conflicts)."""
    rows = import_repository.get_rows_by_property(property_id)
    return [
        r for r in rows
        if r.get("report_type") == "PENDING_MOVE_INS"
        and r.get("conflict_flag")
        and r.get("move_out_date") is None
    ]


def get_fas_rows(property_id: int) -> list[dict]:
    """Return PENDING_FAS import rows for the FAS tracker (units in active phase scope only)."""
    from services import scope_service

    phase_ids = scope_service.get_phase_scope(property_id)
    return import_repository.get_fas_rows(property_id, phase_ids=phase_ids)


def get_diagnostic_rows(property_id: int) -> list[dict]:
    """Return non-OK import rows for the diagnostics tab."""
    rows = import_repository.get_rows_by_property(property_id)
    return [r for r in rows if r.get("validation_status") not in ("OK", None)]


def update_fas_note(property_id: int, row: dict, note_text: str) -> None:
    """Persist FAS note into the row's raw_json."""
    check_writes_enabled()
    import_repository.update_row_note(row["row_id"], note_text)


def run_import_pipeline(
    property_id: int,
    report_type: str,
    file_content: bytes,
    filename: str,
) -> dict:
    """Run the full import pipeline from in-memory file bytes.

    Writes a temp file, delegates to the orchestrator, and returns the
    orchestrator result dict.
    """
    import os
    import tempfile

    check_writes_enabled()

    suffix = os.path.splitext(filename)[1] or ".csv"
    with tempfile.NamedTemporaryFile(
        suffix=suffix, delete=False, mode="wb",
    ) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name

    try:
        from services.imports.orchestrator import import_report_file

        result = import_report_file(
            report_type=report_type,
            file_path=tmp_path,
            property_id=property_id,
        )
    finally:
        os.unlink(tmp_path)

    return result


def get_latest_batch_rows(
    property_id: int, report_type: str,
) -> list[dict]:
    """Return import_row records for the latest completed batch of a report type."""
    batches = import_repository.get_batches_by_property(property_id, limit=200)
    for batch in batches:
        if batch.get("report_type") == report_type and batch.get("status") == "COMPLETED":
            return import_repository.get_rows_by_batch(batch["batch_id"])
    return []


def get_latest_import_timestamps(property_id: int) -> dict[str, str | None]:
    """Return the most recent import timestamp per report type.

    Keys are report types (MOVE_OUTS, PENDING_MOVE_INS, AVAILABLE_UNITS,
    PENDING_FAS).  Values are ISO datetime strings or None if never imported.
    """
    report_types = ["MOVE_OUTS", "PENDING_MOVE_INS", "AVAILABLE_UNITS", "PENDING_FAS"]
    batches = import_repository.get_batches_by_property(property_id, limit=200)

    latest: dict[str, str | None] = {rt: None for rt in report_types}
    for batch in batches:
        rt = batch.get("report_type")
        if rt in latest and batch.get("status") == "COMPLETED":
            ts = batch.get("created_at")
            if ts is not None:
                ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
                if latest[rt] is None or ts_str > latest[rt]:
                    latest[rt] = ts_str
    return latest

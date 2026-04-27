"""Schema validation for import CSV files.

Verifies that the required columns are present for each report type.
No business rules — only structural checks.
"""

from __future__ import annotations

import pandas as pd


class SchemaValidationError(Exception):
    pass


# ── Required columns per report type ─────────────────────────────────────────

REQUIRED_COLUMNS: dict[str, list[str]] = {
    "MOVE_OUTS": ["Unit", "Move-Out Date"],
    "PENDING_MOVE_INS": ["Unit", "Move In Date"],
    "AVAILABLE_UNITS": ["Unit", "Status"],
    "PENDING_FAS": ["Unit", "MO / Cancel Date"],
}

# ── Rows to skip when reading each report type ───────────────────────────────

SKIPROWS: dict[str, int] = {
    "MOVE_OUTS": 6,
    "PENDING_MOVE_INS": 5,
    "AVAILABLE_UNITS": 5,
    "PENDING_FAS": 4,
}


def validate_import_schema(report_type: str, file_path: str) -> None:
    """Ensure the CSV at *file_path* contains the required columns for
    *report_type*.

    Raises ``SchemaValidationError`` when required columns are missing.
    """
    required = REQUIRED_COLUMNS.get(report_type)
    if required is None:
        raise SchemaValidationError(f"Unknown report type: {report_type}")

    skiprows = SKIPROWS.get(report_type, 0)

    try:
        df = pd.read_csv(file_path, skiprows=skiprows, nrows=0)
    except Exception as exc:
        raise SchemaValidationError(f"Unable to read CSV for schema validation: {exc}") from exc

    # Pending FAS has "Unit Number" in the raw file — rename to "Unit"
    if report_type == "PENDING_FAS" and "Unit Number" in df.columns and "Unit" not in df.columns:
        df = df.rename(columns={"Unit Number": "Unit"})

    actual = set(df.columns)
    missing = [col for col in required if col not in actual]

    if missing:
        raise SchemaValidationError(
            f"Missing required columns for {report_type}: {missing}. Found: {sorted(actual)}"
        )

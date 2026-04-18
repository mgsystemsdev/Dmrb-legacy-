"""File-level validation for import files.

Checks file existence, type, and size.  No business rules.
"""

from __future__ import annotations

import os


class FileValidationError(Exception):
    pass


def validate_import_file(file_path: str) -> None:
    """Validate that *file_path* points to a non-empty CSV file.

    Raises ``FileValidationError`` on any failure.
    """
    if not os.path.exists(file_path):
        raise FileValidationError(f"File not found: {file_path}")

    if not file_path.lower().endswith(".csv"):
        raise FileValidationError(
            f"Unsupported file type: {file_path}. Only CSV files are accepted."
        )

    if os.path.getsize(file_path) == 0:
        raise FileValidationError(f"File is empty: {file_path}")

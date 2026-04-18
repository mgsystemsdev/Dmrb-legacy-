"""Import Reports screen — standalone entry point for the import console."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services import import_service
from services.import_service import ImportError as ImportBatchError
from services.report_operations import missing_move_out_service
from ui.helpers.formatting import format_date


_IMPORT_TYPES = [
    ("AVAILABLE_UNITS", "Available Units"),
    ("MOVE_OUTS", "Move Outs"),
    ("PENDING_MOVE_INS", "Pending Move-Ins"),
    ("PENDING_FAS", "Final Account Statement (FAS)"),
]


def render_import_console() -> None:
    st.title("Import Reports")

    property_id = st.session_state.get("property_id")
    if property_id is None:
        st.info("Create a property in the Admin tab to begin.")
        return

    missing_move_out_service.reconcile_pending_move_ins(property_id)

    with st.container(border=True):
        st.markdown("**IMPORT CONSOLE**")

        sub_tabs = st.tabs([label for _, label in _IMPORT_TYPES])

        for (report_type, label), sub_tab in zip(_IMPORT_TYPES, sub_tabs):
            with sub_tab:
                _render_import_sub(property_id, report_type, label)


def _render_import_sub(property_id: int, report_type: str, label: str) -> None:
    uc1, uc2 = st.columns([2, 1])
    with uc1:
        file = st.file_uploader(
            f"{label}.csv", key=f"ic_import_file_{report_type}", type=["csv", "xlsx"],
        )
    with uc2:
        st.write("")
        if st.button(
            f"Run {label} import", key=f"ic_import_run_{report_type}",
            width="stretch",
        ):
            if file is None:
                st.warning("Upload a file first.")
            else:
                try:
                    content = file.read()
                    result = import_service.run_import_pipeline(
                        property_id, report_type, content, file.name,
                    )
                    status = result.get("status", "UNKNOWN")
                    if status == "SUCCESS":
                        st.success(
                            f"Batch #{result.get('batch_id')} completed — "
                            f"{result.get('record_count', 0)} rows "
                            f"({result.get('applied_count', 0)} applied, "
                            f"{result.get('conflict_count', 0)} conflicts, "
                            f"{result.get('invalid_count', 0)} invalid)."
                        )
                    elif status == "NO_OP":
                        st.info("File already imported (duplicate).")
                    else:
                        diags = result.get("diagnostics", [])
                        st.error(f"Import failed: {'; '.join(diags) or status}")
                    st.cache_data.clear()
                    st.rerun()
                except (ImportBatchError, Exception) as exc:
                    st.error(str(exc))

    # Latest batch info
    batches = import_service.get_history(property_id, limit=5)
    matched = [b for b in batches if b.get("report_type") == report_type]
    if matched:
        latest = matched[0]
        ts = format_date(latest.get("created_at"))
        count = latest.get("record_count", 0)
        status = latest.get("status", "—")
        st.caption(f"Latest import: {ts} · {count} rows · {status}")
    else:
        st.caption("No imports yet.")

    # Full data table with status/conflict/imported
    _render_import_rows_full(property_id, report_type)

    # Clean data-only table
    _render_import_rows_clean(property_id, report_type, label)

    if report_type == "AVAILABLE_UNITS":
        st.caption(
            "On Notice units whose available date has passed are treated as Vacant Not Ready "
            "when the board loads (computed status); turnovers are created automatically if missing."
        )


def _render_import_rows_full(property_id: int, report_type: str) -> None:
    """Full import rows table — latest batch, with raw CSV values + outcome."""
    rows = import_service.get_latest_batch_rows(property_id, report_type)
    if not rows:
        st.caption("No imported rows.")
        return

    if report_type == "AVAILABLE_UNITS":
        table = []
        for r in rows:
            raw = r.get("raw_json") or {}
            table.append({
                "validation_status": r.get("validation_status", ""),
                "conflict_flag": r.get("conflict_flag", False),
                "conflict_reason": r.get("conflict_reason") or "—",
                "Unit": raw.get("Unit", r.get("unit_code_norm", "")),
                "Status": raw.get("Status", ""),
                "Available Date": raw.get("Available Date", ""),
                "Move-In Ready Date": raw.get("Move-In Ready Date", ""),
            })
    elif report_type == "MOVE_OUTS":
        table = []
        for r in rows:
            raw = r.get("raw_json") or {}
            table.append({
                "validation_status": r.get("validation_status", ""),
                "conflict_reason": r.get("conflict_reason") or "—",
                "Unit": raw.get("Unit", r.get("unit_code_norm", "")),
                "Move-Out Date": raw.get("Move-Out Date", ""),
            })
    elif report_type == "PENDING_MOVE_INS":
        table = []
        for r in rows:
            raw = r.get("raw_json") or {}
            table.append({
                "validation_status": r.get("validation_status", ""),
                "conflict_reason": r.get("conflict_reason") or "—",
                "Unit": raw.get("Unit", r.get("unit_code_norm", "")),
                "Move In Date": raw.get("Move In Date", ""),
            })
    elif report_type == "PENDING_FAS":
        table = []
        for r in rows:
            raw = r.get("raw_json") or {}
            table.append({
                "validation_status": r.get("validation_status", ""),
                "Unit": raw.get("Unit", r.get("unit_code_norm", "")),
                "MO / Cancel Date": raw.get("MO / Cancel Date", ""),
                "Note": raw.get("note_text") or "—",
            })
    else:
        table = [
            {
                "Unit": r.get("unit_code_norm", ""),
                "validation_status": r.get("validation_status", ""),
            }
            for r in rows
        ]

    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)


def _render_import_rows_clean(property_id: int, report_type: str, label: str) -> None:
    """Clean data-only table — CSV values only (no outcome columns)."""
    rows = import_service.get_latest_batch_rows(property_id, report_type)
    if not rows:
        return

    if report_type == "AVAILABLE_UNITS":
        table = []
        for r in rows:
            raw = r.get("raw_json") or {}
            table.append({
                "Unit": raw.get("Unit", r.get("unit_code_norm", "")),
                "Status": raw.get("Status", ""),
                "Available Date": raw.get("Available Date", ""),
                "Move-In Ready Date": raw.get("Move-In Ready Date", ""),
            })
    elif report_type == "MOVE_OUTS":
        table = []
        for r in rows:
            raw = r.get("raw_json") or {}
            table.append({
                "Unit": raw.get("Unit", r.get("unit_code_norm", "")),
                "Move-Out Date": raw.get("Move-Out Date", ""),
            })
    elif report_type == "PENDING_MOVE_INS":
        table = []
        for r in rows:
            raw = r.get("raw_json") or {}
            table.append({
                "Unit": raw.get("Unit", r.get("unit_code_norm", "")),
                "Move In Date": raw.get("Move In Date", ""),
            })
    elif report_type == "PENDING_FAS":
        table = []
        for r in rows:
            raw = r.get("raw_json") or {}
            table.append({
                "Unit": raw.get("Unit", r.get("unit_code_norm", "")),
                "MO / Cancel Date": raw.get("MO / Cancel Date", ""),
            })
    else:
        table = [{"Unit": r.get("unit_code_norm", "")} for r in rows]

    with st.container(border=True):
        st.markdown(f"**{label.upper()}**")
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

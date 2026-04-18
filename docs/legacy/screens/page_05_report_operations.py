"""
Page 5 — Report Operations (skeleton).
Layout-only: title, three tabs (Missing Move-Out, FAS Tracker, Import Diagnostics). Placeholder data only.
Run standalone: streamlit run docs/skeleton_pages/page_05_report_operations.py
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st


def _placeholder_has_active_property() -> bool:
    return True


def _placeholder_missing_move_out():
    """List of dicts: unit_code, report_type, move_in_date, conflict_reason, imported_at. Empty → info."""
    return [
        {
            "unit_code": "5-1-101",
            "report_type": "PENDING_MOVE_INS",
            "move_in_date": "2025-03-10",
            "conflict_reason": "No move-out on file",
            "imported_at": "2025-03-13 09:00",
        },
    ]


def _placeholder_fas_rows():
    """List of dicts: unit_code, fas_date, imported_at, note_text. Empty → info."""
    return [
        {"unit_code": "7-2-205", "fas_date": "2025-03-01", "imported_at": "2025-03-13 09:00", "note_text": "Checked"},
    ]


def _placeholder_import_diagnostics():
    """List of dicts: unit_code, report_type, validation_status, conflict_reason, imported_at, source_file. Empty → info."""
    return [
        {
            "unit_code": "8-1-102",
            "report_type": "MOVE_OUTS",
            "validation_status": "CONFLICT",
            "conflict_reason": "Duplicate",
            "imported_at": "2025-03-13 08:30",
            "source_file": "move_outs.csv",
        },
    ]


def render() -> None:
    st.title("Report Operations")

    if not _placeholder_has_active_property():
        st.info("Create a property in the Admin tab to begin.")
        return
    st.caption("Active Property: **Sample Property**")

    tab1, tab2, tab3 = st.tabs(["Missing Move-Out", "FAS Tracker", "Import Diagnostics"])

    # ---------- Tab 1: Missing Move-Out ----------
    with tab1:
        st.subheader("Missing Move-Out Queue")
        st.caption(
            "Move-in rows without move-out are repaired here. "
            "Enter a move-out date to create the turnover. "
            "Units will appear on the board only after turnover creation. "
            "This makes the workflow obvious for managers."
        )
        rows_mo = _placeholder_missing_move_out()
        if not rows_mo:
            st.info("No missing move-out exceptions for the active property.")
        else:
            df_mo = pd.DataFrame([
                {
                    "Unit": r.get("unit_code"),
                    "Report type": r.get("report_type"),
                    "Move-in date": r.get("move_in_date") or "—",
                    "Conflict reason": r.get("conflict_reason"),
                    "Import timestamp": r.get("imported_at") or "—",
                }
                for r in rows_mo
            ])
            st.dataframe(df_mo, use_container_width=True, hide_index=True)
        st.markdown("---")
        st.markdown("**Resolve: create turnover with move-out date**")
        options_mo = [f"{r.get('unit_code')} ({r.get('conflict_reason')})" for r in rows_mo] if rows_mo else ["—"]
        st.selectbox("Select unit to resolve", options=options_mo, key="sk_ro_missing_unit")
        st.date_input("Move-out date", value=date.today(), key="sk_ro_move_out_date")
        st.button("Create turnover", key="sk_ro_create_turnover")

    # ---------- Tab 2: FAS Tracker ----------
    with tab2:
        st.subheader("Final Account Statement Tracker")
        st.caption(
            "Units from Pending FAS imports. Add or edit notes (e.g. Done, Checked, Keys returned); "
            "notes persist across imports."
        )
        rows_fas = _placeholder_fas_rows()
        if not rows_fas:
            st.info("No PENDING_FAS import rows for the active property.")
        else:
            df_fas = pd.DataFrame([
                {
                    "Unit": r.get("unit_code"),
                    "FAS date": r.get("fas_date") or "—",
                    "Import timestamp": r.get("imported_at") or "—",
                    "Note": r.get("note_text") or "",
                }
                for r in rows_fas
            ])
            st.dataframe(df_fas, use_container_width=True, hide_index=True)
        st.markdown("---")
        st.markdown("**Edit note**")
        options_fas = [f"{r.get('unit_code')} | {r.get('fas_date') or '—'}" for r in rows_fas] if rows_fas else ["—"]
        st.selectbox("Select row", options=options_fas, key="sk_ro_fas_row")
        st.text_input("Note", value="", key="sk_ro_fas_note", placeholder="e.g. Done, Checked, Keys returned")
        st.button("Save note", key="sk_ro_fas_save")

    # ---------- Tab 3: Import Diagnostics ----------
    with tab3:
        st.subheader("Import Diagnostics")
        st.caption(
            "Non-OK import outcomes (ignored, conflict, invalid, skipped override). "
            "Observational only; no state changes from this tab."
        )
        rows_diag = _placeholder_import_diagnostics()
        if not rows_diag:
            st.info("No diagnostic rows for the active property.")
        else:
            df_diag = pd.DataFrame([
                {
                    "Unit": r.get("unit_code"),
                    "Report type": r.get("report_type"),
                    "Status": r.get("validation_status"),
                    "Conflict reason": r.get("conflict_reason") or "—",
                    "Import time": r.get("imported_at") or "—",
                    "Source file": r.get("source_file") or "—",
                }
                for r in rows_diag
            ])
            st.dataframe(df_diag, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Report Operations (skeleton)")
    render()

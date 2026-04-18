"""Report Operations screen — Missing Move-Out, FAS Tracker, Import Diagnostics."""

from __future__ import annotations


import pandas as pd
import streamlit as st

from services import import_service, turnover_service, property_service
from services.report_operations import (
    missing_move_out_service,
    override_conflict_service,
    invalid_data_service,
    import_diagnostics_service,
)
from ui.helpers.formatting import format_date


def render_import_reports() -> None:
    st.title("Report Operations")

    property_id = st.session_state.get("property_id")
    if property_id is None:
        st.info("Create a property in the Admin tab to begin.")
        return

    st.caption(f"Active Property: **{_property_name(property_id)}**")

    tab1, tab2, tab3 = st.tabs([
        "Override Conflicts", "Invalid Data", "Import Diagnostics",
    ])

    with tab1:
        _render_override_conflicts(property_id)

    with tab2:
        _render_invalid_data(property_id)

    with tab3:
        _render_import_diagnostics(property_id)


# ── Tab 1: Missing Move-Out ─────────────────────────────────────────────────

def render_missing_move_out(property_id: int) -> None:
    st.subheader("Missing Move-Out Queue")
    st.caption(
        "Pick a move-out date in the **Move-Out** column to create the turnover. "
        "The row disappears once resolved."
    )

    rows = missing_move_out_service.list_missing_move_outs(property_id)

    if not rows:
        st.info("No missing move-out exceptions for the active property.")
        return

    df = pd.DataFrame([
        {
            "Unit": r.get("unit_code_norm", ""),
            "Move-In": r.get("move_in_date"),
            "Batch": format_date(r.get("batch_created_at")),
            "Detected": format_date(r.get("created_at")),
            "Move-Out": None,
        }
        for r in rows
    ])

    edited = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=["Unit", "Move-In", "Batch", "Detected"],
        column_config={
            "Unit": st.column_config.TextColumn("Unit"),
            "Move-In": st.column_config.DateColumn("Move-In", format="MM/DD/YYYY"),
            "Batch": st.column_config.TextColumn("Report Batch"),
            "Detected": st.column_config.TextColumn("Detected At"),
            "Move-Out": st.column_config.DateColumn("Move-Out", format="MM/DD/YYYY"),
        },
        key="ro_missing_editor",
    )

    created = 0
    for idx, row_data in edited.iterrows():
        if row_data["Move-Out"] is not None and idx < len(rows):
            raw = rows[idx]
            unit = turnover_service.search_unit(property_id, raw["unit_code_norm"])
            if unit is None:
                st.error(f"Unit {raw['unit_code_norm']} not found.")
                continue
            try:
                move_out = row_data["Move-Out"]
                if isinstance(move_out, pd.Timestamp):
                    move_out = move_out.date()
                new = missing_move_out_service.resolve_missing_move_out(
                    row_id=raw["row_id"],
                    property_id=property_id,
                    unit_id=unit["unit_id"],
                    move_out_date=move_out,
                    move_in_date=raw.get("move_in_date"),
                    actor="manager",
                )
                st.success(f"Turnover #{new['turnover_id']} created for **{raw['unit_code_norm']}**.")
                created += 1
            except turnover_service.TurnoverError as exc:
                st.error(f"{raw['unit_code_norm']}: {exc}")

    if created:
        st.cache_data.clear()
        st.rerun()


# ── Tab 2: Override Conflicts ────────────────────────────────────────────────

def _render_override_conflicts(property_id: int) -> None:
    st.subheader("Override Conflicts")
    st.caption(
        "Fields skipped during import because a manual override was active "
        "and the report value differed. Choose **Keep Manual** or **Accept Report** for each."
    )

    rows = override_conflict_service.list_override_conflicts(property_id)

    if not rows:
        st.info("No unresolved override conflicts for the active property.")
        return

    for idx, r in enumerate(rows):
        with st.container():
            cols = st.columns([2, 2, 2, 2, 2, 2])
            cols[0].markdown(f"**{r['unit']}**")
            cols[1].text(r["conflict_field"])
            cols[2].text(r["manual_value"] or "—")
            cols[3].text(r["report_value"] or "—")
            cols[4].text(format_date(r["detected_at"]))

            action_cols = cols[5].columns(2)
            keep_key = f"ro_oc_keep_{r['row_id']}_{r['conflict_field']}_{idx}"
            accept_key = f"ro_oc_accept_{r['row_id']}_{r['conflict_field']}_{idx}"

            if action_cols[0].button("Keep Manual", key=keep_key):
                override_conflict_service.resolve_override_conflict(
                    row_id=r["row_id"],
                    turnover_id=r["turnover_id"],
                    conflict_field=r["conflict_field"],
                    action="keep_manual",
                    property_id=property_id,
                )
                st.success(f"Kept manual value for **{r['unit']}** → {r['conflict_field']}.")
                st.cache_data.clear()
                st.rerun()

            if action_cols[1].button("Accept Report", key=accept_key):
                override_conflict_service.resolve_override_conflict(
                    row_id=r["row_id"],
                    turnover_id=r["turnover_id"],
                    conflict_field=r["conflict_field"],
                    action="accept_report",
                    report_value=r["report_value"],
                    property_id=property_id,
                )
                st.success(f"Applied report value for **{r['unit']}** → {r['conflict_field']}.")
                st.cache_data.clear()
                st.rerun()

    # Summary table for quick scanning
    st.markdown("---")
    df = pd.DataFrame([
        {
            "Unit": r["unit"],
            "Field": r["conflict_field"],
            "Manual Value": r["manual_value"] or "—",
            "Report Value": r["report_value"] or "—",
            "Detected": format_date(r["detected_at"]),
        }
        for r in rows
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)


# ── Tab 3: Invalid Data ─────────────────────────────────────────────────────

def _render_invalid_data(property_id: int) -> None:
    st.subheader("Invalid Data Queue")
    st.caption(
        "Import rows that failed because required data was missing or malformed. "
        "Supply a corrected value and click **Apply Correction** to resolve."
    )

    rows = invalid_data_service.list_invalid_rows(property_id)

    if not rows:
        st.info("No unresolved invalid-data rows for the active property.")
        return

    resolved = 0
    for idx, r in enumerate(rows):
        with st.expander(
            f"{r['unit']}  —  {r['reason']}  —  {format_date(r['detected_at'])}",
            expanded=False,
        ):
            st.markdown(
                f"**Batch** {r['batch_id']}  ·  **Report** {r['report_type']}"
            )

            # Show existing raw values for context
            raw = r.get("raw_json") or {}
            if raw:
                st.json(raw)

            # Corrected value input — the field depends on the report type
            corrected_date = st.date_input(
                "Corrected date",
                value=None,
                key=f"ro_inv_date_{r['row_id']}_{idx}",
            )

            if st.button("Apply Correction", key=f"ro_inv_apply_{r['row_id']}_{idx}"):
                if corrected_date is None:
                    st.warning("Enter a corrected date before applying.")
                else:
                    field = _target_field(r["report_type"])
                    try:
                        invalid_data_service.resolve_invalid_row(
                            row_id=r["row_id"],
                            corrected_fields={
                                field: corrected_date,
                                "unit_code_norm": r["unit"],
                            },
                            property_id=property_id,
                        )
                        st.success(
                            f"Correction applied for **{r['unit']}** "
                            f"({field} = {corrected_date})."
                        )
                        resolved += 1
                    except (ValueError, Exception) as exc:
                        st.error(str(exc))

    if resolved:
        st.cache_data.clear()
        st.rerun()


def _target_field(report_type: str) -> str:
    """Map report type to the turnover field the correction targets."""
    return {
        "MOVE_OUTS": "move_out_date",
        "PENDING_MOVE_INS": "move_in_date",
        "AVAILABLE_UNITS": "available_date",
        "PENDING_FAS": "confirmed_move_out_date",
    }.get(report_type, "move_out_date")


# ── Tab 4: FAS Tracker ──────────────────────────────────────────────────────

def render_fas_tracker(property_id: int) -> None:
    st.subheader("Final Account Statement Tracker")
    st.caption(
        "Units from Pending FAS imports. Edit notes directly in the table, "
        "then click **Save Changes** to persist."
    )

    rows = import_service.get_fas_rows(property_id)

    if not rows:
        st.info("No PENDING_FAS import rows for the active property.")
        return

    df = pd.DataFrame([
        {
            "row_id": r.get("row_id"),
            "Unit": r.get("unit_code_norm", ""),
            "FAS date": format_date(r.get("fas_date")),
            "Import timestamp": format_date(r.get("imported_at")),
            "Note": r.get("note_text") or "",
        }
        for r in rows
    ])

    edited = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=["row_id", "Unit", "FAS date", "Import timestamp"],
        column_config={
            "row_id": None,
            "Unit": st.column_config.TextColumn("Unit"),
            "FAS date": st.column_config.TextColumn("FAS date"),
            "Import timestamp": st.column_config.TextColumn("Import timestamp"),
            "Note": st.column_config.TextColumn("Note"),
        },
        key="ro_fas_editor",
    )

    if st.button("Save Changes", key="ro_fas_save"):
        saved = 0
        for idx, row_data in edited.iterrows():
            if idx < len(rows):
                old_note = rows[idx].get("note_text") or ""
                new_note = row_data["Note"] or ""
                if new_note != old_note:
                    import_service.update_fas_note(
                        property_id, rows[idx], new_note,
                    )
                    saved += 1
        if saved:
            st.success(f"Saved {saved} note(s).")
            st.cache_data.clear()
            st.rerun()
        else:
            st.info("No changes detected.")


# ── Tab 5: Import Diagnostics ───────────────────────────────────────────────

def _render_import_diagnostics(property_id: int) -> None:
    st.subheader("Import Diagnostics")
    st.caption(
        "Recent import batches and their row-level outcomes. "
        "Expand a batch to inspect individual rows."
    )

    batches = import_diagnostics_service.list_import_batches(property_id)

    if not batches:
        st.info("No import batches for the active property.")
        return

    # ── Batch summary table ──────────────────────────────────────────────
    df = pd.DataFrame([
        {
            "Batch": b["batch_id"],
            "Report Type": b["report_type"],
            "Imported": format_date(b["created_at"]),
            "Records": b["record_count"],
            "Applied": b["applied_count"],
            "Conflicts": b["conflict_count"],
            "Invalid": b["invalid_count"],
            "Status": b["status"],
        }
        for b in batches
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Drill-down into a single batch ───────────────────────────────────
    st.markdown("---")
    batch_options = {
        b["batch_id"]: (
            f"#{b['batch_id']}  —  {b['report_type']}  —  "
            f"{format_date(b['created_at'])}"
        )
        for b in batches
    }
    selected = st.selectbox(
        "Inspect batch",
        options=list(batch_options.keys()),
        format_func=lambda bid: batch_options[bid],
        key="ro_diag_batch",
    )

    if selected is not None:
        rows = import_diagnostics_service.get_batch_details(selected)
        if not rows:
            st.info("No rows recorded for this batch.")
        else:
            row_df = pd.DataFrame([
                {
                    "Unit": r.get("unit") or "—",
                    "Status": r["validation_status"],
                    "Conflict Reason": r.get("conflict_reason") or "—",
                    "Move-Out": format_date(r.get("move_out_date")),
                    "Move-In": format_date(r.get("move_in_date")),
                }
                for r in rows
            ])
            st.dataframe(row_df, use_container_width=True, hide_index=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _property_name(property_id: int) -> str:
    props = property_service.get_all_properties()
    for p in props:
        if p["property_id"] == property_id:
            return p["name"]
    return f"Property {property_id}"

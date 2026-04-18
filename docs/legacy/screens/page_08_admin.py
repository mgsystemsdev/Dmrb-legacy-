"""
Page 8 — Admin (skeleton).
Layout-only: control bar (DB Writes, Active Property, New Property), five tabs.
Placeholder data only. Run standalone: streamlit run docs/skeleton_pages/page_08_admin.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Placeholder options
# ---------------------------------------------------------------------------
TASK_DISPLAY_NAMES = [
    ("Insp", "Inspection"),
    ("CB", "Carpet Bid"),
    ("MR", "Make Ready"),
    ("QC", "Quality Control"),
]
EXEC_LABELS = ["Not Started", "In Progress", "Done"]
CONFIRM_LABELS = ["Pending", "Confirmed"]
BLOCK_OPTS = ["Not Blocking", "Vendor Delay", "Other"]
OFFSET_OPTS = list(range(1, 11))


def render() -> None:
    st.subheader("Admin")

    # ---------- Control bar: [1.2, 1.6, 1.6] ----------
    admin_col1, admin_col2, admin_col3 = st.columns([1.2, 1.6, 1.6])
    with admin_col1:
        st.checkbox(
            "Enable DB Writes (⚠ irreversible)",
            value=st.session_state.get("sk_enable_db_writes", False),
            key="sk_enable_db_writes",
        )
    with admin_col2:
        st.selectbox(
            "Active Property",
            ["Sample Property (id=1)", "Other Property (id=2)"],
            index=0,
            key="sk_admin_property",
        )
    with admin_col3:
        st.text_input("New Property", value="", key="sk_admin_new_property", placeholder="Property name")
        st.button("Create Property", key="sk_admin_create_property")

    st.caption("DB writes are **off**. You can browse and export; turn this on here to save changes.")
    st.caption("Active Property: Sample Property")

    tab_add, tab_import, tab_unit_master, tab_export, tab_dropdown = st.tabs(
        ["Add Unit", "Import", "Unit Master Import", "Exports", "Dropdown Manager"]
    )

    # ---------- Tab: Add Unit ----------
    with tab_add:
        st.subheader("Add unit")
        st.caption(
            "Add unit to active turnover. Unit must already exist in the database; one open turnover per unit."
        )
        st.selectbox("Phase", ["5", "7", "8"], key="sk_add_phase")
        st.selectbox("Building", ["1", "2"], key="sk_add_building")
        st.text_input("Unit", key="sk_add_unit_number")
        st.date_input("Move out", key="sk_add_move_out")
        st.date_input("Ready date (optional)", value=None, key="sk_add_ready")
        st.date_input("Move in (optional)", value=None, key="sk_add_move_in")
        st.button("Add unit", key="sk_add_submit")

    # ---------- Tab: Import (4 sub-tabs) ----------
    with tab_import:
        st.subheader("Import console")
        tab_au, tab_mo, tab_pmi, tab_fas = st.tabs(
            ["Available Units", "Move Outs", "Pending Move-Ins", "Final Account Statement (FAS)"]
        )
        with tab_au:
            st.file_uploader("Available Units.csv", key="sk_import_au", type=["csv"])
            st.button("Run Available Units import", key="sk_import_run_au")
            st.markdown("### Available Units — Latest import")
            st.caption("Imported: 2025-03-13 09:00 | Rows: 42 | Status: OK")
            st.dataframe(pd.DataFrame([{"Unit": "5-1-101", "Status": "Vacant", "Available Date": "03/15/2025"}]), use_container_width=True, hide_index=True)
            st.markdown("---")
            st.caption("Use the button below to reapply the latest Available Units report's Move-In Ready Date and Status onto existing turnovers.")
            st.button("Apply latest Available Units readiness to turnovers", key="sk_import_reapply_au")
        with tab_mo:
            st.file_uploader("Move Outs.csv", key="sk_import_mo", type=["csv"])
            st.button("Run Move Outs import", key="sk_import_run_mo")
            st.markdown("### Move Outs — Latest import")
            st.caption("Imported: 2025-03-13 09:00 | Rows: 10")
            st.dataframe(pd.DataFrame([{"Unit": "5-1-101", "Move-Out Date": "03/01/2025"}]), use_container_width=True, hide_index=True)
        with tab_pmi:
            st.file_uploader("Pending Move-Ins.csv", key="sk_import_pmi", type=["csv"])
            st.button("Run Pending Move-Ins import", key="sk_import_run_pmi")
            st.markdown("### Pending Move-Ins — Latest import")
            st.caption("Imported: 2025-03-13 09:00")
        with tab_fas:
            st.file_uploader("Pending FAS.csv", key="sk_import_fas", type=["csv"])
            st.button("Run FAS import", key="sk_import_run_fas")
            st.markdown("### FAS — Latest import")
            st.caption("Imported: —")
        st.subheader("Conflicts")
        st.caption("Conflict details are recorded in import_row for the batch. List conflicts here when a batch is selected (future).")

    # ---------- Tab: Unit Master Import ----------
    with tab_unit_master:
        st.subheader("Unit Master Import")
        st.caption(
            "One-time structural bootstrap from Units.csv. Writes only to unit (and phase/building when creating units)."
        )
        st.checkbox("Strict mode (fail if unit not found; no creates)", value=False, key="sk_um_strict")
        st.file_uploader("Units.csv", type=["csv"], key="sk_um_file")
        st.button("Run Unit Master Import", key="sk_um_run")
        st.markdown("### Unit Master Import — Imported Units")
        st.dataframe(
            pd.DataFrame([{"unit_id": 1, "unit_code": "5-1-101", "phase_code": "5", "building_code": "1"}]),
            use_container_width=True,
            hide_index=True,
        )

    # ---------- Tab: Exports ----------
    with tab_export:
        st.subheader("Export Reports")
        st.caption(
            "Exports always include all open turnovers, regardless of current screen filters."
        )
        if st.button("Prepare Export Files", key="sk_export_prepare"):
            st.session_state.sk_export_ready = True
            st.rerun()
        if st.session_state.get("sk_export_ready"):
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("Download Final Report (XLSX)", data=b"", file_name="Final_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="sk_dl_final")
                st.download_button("Download DMRB Report (XLSX)", data=b"", file_name="DMRB_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="sk_dl_dmrb")
                st.download_button("Download Dashboard Chart (PNG)", data=b"", file_name="Dashboard_Chart.png", mime="image/png", key="sk_dl_chart")
            with c2:
                st.download_button("Download Weekly Summary (TXT)", data=b"", file_name="Weekly_Summary.txt", mime="text/plain", key="sk_dl_weekly")
                st.download_button("Download All Reports (ZIP)", data=b"", file_name="DMRB_Reports.zip", mime="application/zip", key="sk_dl_zip")
        else:
            st.info("Click 'Prepare Export Files' to generate downloads.")

    # ---------- Tab: Dropdown Manager ----------
    with tab_dropdown:
        st.subheader("Dropdown Manager")
        st.caption(
            "Manage assignees per task type. Execution statuses, confirmation statuses, "
            "and blocking reasons are system-controlled and cannot be changed here."
        )
        with st.container(border=True):
            st.markdown("**TASK ASSIGNEES**")
            st.caption("Add or remove assignees for each task type.")
            for code, display_name in TASK_DISPLAY_NAMES:
                with st.expander(f"{display_name} — 2 assignee(s)"):
                    st.write("Alice")
                    st.button("Remove", key=f"sk_dd_rm_{code}_0")
                    st.write("Bob")
                    st.button("Remove", key=f"sk_dd_rm_{code}_1")
                    st.text_input("Add assignee", key=f"sk_dd_add_{code}", placeholder="Name...")
                    st.button("Add", key=f"sk_dd_add_btn_{code}")
        with st.container(border=True):
            st.markdown("**TASK OFFSET SCHEDULE**")
            st.caption("Days after move-out when each task is scheduled. Select an offset and hit Save.")
            for code, display_name in TASK_DISPLAY_NAMES:
                c1, c2, c3 = st.columns([2, 1.5, 1])
                c1.write(f"**{display_name}**")
                c2.selectbox("Offset", OFFSET_OPTS, index=0, key=f"sk_dd_offset_{code}", label_visibility="collapsed")
                c3.button("Save", key=f"sk_dd_offset_save_{code}")
            st.divider()
            st.caption("Current schedule (days after move-out):")
            st.write("Day 1 → Inspection")
            st.write("Day 2 → Carpet Bid")
            st.write("Day 5 → Make Ready")
            st.write("Day 9 → Quality Control")
        with st.container(border=True):
            st.markdown("**SYSTEM-CONTROLLED VALUES** *(read-only — managed by backend)*")
            r1, r2, r3 = st.columns(3)
            with r1:
                st.caption("Execution Statuses")
                for label in EXEC_LABELS:
                    st.write(f"· {label}")
            with r2:
                st.caption("Confirmation Statuses")
                for label in CONFIRM_LABELS:
                    st.write(f"· {label}")
            with r3:
                st.caption("Blocking Reasons")
                for label in BLOCK_OPTS:
                    st.write(f"· {label}")

    # ---------- Property structure (read-only) ----------
    st.subheader("Property structure")
    st.caption("Read-only view: property → phase → building → unit.")
    with st.expander("**Sample Property** (id=1)", expanded=True):
        st.markdown("Phase **5** (id=1)")
        st.caption("  Building 1 (id=1): units 101, 102, 103")
        st.caption("  Building 2 (id=2): units 201, 202")


if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Admin (skeleton)")
    if "sk_export_ready" not in st.session_state:
        st.session_state.sk_export_ready = False
    render()

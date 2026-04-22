"""Export Reports screen — all export artifacts from a single board load."""

from __future__ import annotations

from datetime import date

import streamlit as st

from services import board_service, property_service, scope_service
from services.exports import export_chart, export_excel, export_service

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_EXPORT_STATE_KEYS = (
    "weekly_summary_bytes",
    "final_report_bytes",
    "dmrb_report_bytes",
    "chart_bytes",
    "zip_bytes",
    "export_turnover_count",
    "export_prepared_date",
)


def render_export_reports() -> None:
    st.title("Export Reports")

    property_id = st.session_state.get("property_id")
    if property_id is None:
        st.info("Create a property in the Admin tab to begin.")
        return

    st.caption(f"Active Property: **{_property_name(property_id)}**")

    with st.container(border=True):
        st.markdown("**EXPORT CONSOLE**")
        st.caption(
            "Builds every export from one board load for the active property. "
            "Uses the current phase scope and open turnovers only."
        )
        ec1, ec2 = st.columns([2, 1])
        with ec1:
            st.markdown(
                "Run **Prepare** to regenerate all files. Downloads below use the "
                "last successful prepare until you run it again."
            )
            _export_last_prepare_caption()
        with ec2:
            st.write("")
            if st.button("Prepare Export Files", key="export_prepare", width="stretch"):
                try:
                    today = date.today()
                    uid = int(st.session_state.get("user_id") or 0)
                    phase_scope = scope_service.get_phase_scope(uid, property_id)
                    board = board_service.get_board(
                        property_id, today=today, phase_scope=phase_scope
                    )
                    metrics = board_service.get_board_metrics(
                        property_id=property_id, board=board, user_id=uid
                    )
                    rows = export_service.build_export_turnovers(
                        property_id,
                        today=today,
                        phase_scope=phase_scope,
                        board=board,
                        user_id=uid,
                    )
                    st.session_state.weekly_summary_bytes = (
                        export_service.build_weekly_summary_bytes(
                            property_id,
                            today=today,
                            phase_scope=phase_scope,
                            board=board,
                            user_id=uid,
                        )
                    )
                    st.session_state.final_report_bytes = export_excel.build_final_report(rows)
                    st.session_state.dmrb_report_bytes = export_excel.build_dmrb_report(
                        rows, metrics, today
                    )
                    st.session_state.chart_bytes = export_chart.build_dashboard_chart(
                        rows, today
                    )
                    st.session_state.zip_bytes = export_service.build_all_exports_zip_from_parts(
                        st.session_state.final_report_bytes,
                        st.session_state.dmrb_report_bytes,
                        st.session_state.chart_bytes,
                        st.session_state.weekly_summary_bytes,
                    )
                    st.session_state.export_prepare_error = None
                    st.session_state.export_turnover_count = len(rows)
                    st.session_state.export_prepared_date = today.isoformat()
                except Exception as exc:  # noqa: BLE001 — surface to operator
                    for k in _EXPORT_STATE_KEYS:
                        st.session_state[k] = None
                    st.session_state.export_prepare_error = str(exc)
                st.rerun()

    err = st.session_state.get("export_prepare_error")
    if err:
        st.error(f"Export preparation failed: {err}")

    with st.container(border=True):
        st.markdown("**DOWNLOADS**")
        st.caption(
            "Each tab groups related files. Empty downloads mean nothing has been "
            "prepared yet or the last prepare failed."
        )
        if not _exports_ready():
            st.info("Click **Prepare Export Files** in the console above to generate downloads.")

        tab_xlsx, tab_misc, tab_zip = st.tabs(
            ["Excel reports", "Summary & chart", "Full package"]
        )

        with tab_xlsx:
            st.caption("Workbooks derived from the current board export rows.")
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "Download Final Report (XLSX)",
                    data=st.session_state.get("final_report_bytes") or b"",
                    file_name="Final_Report.xlsx",
                    mime=_XLSX_MIME,
                    key="export_dl_final",
                )
            with c2:
                st.download_button(
                    "Download DMRB Report (XLSX)",
                    data=st.session_state.get("dmrb_report_bytes") or b"",
                    file_name="DMRB_Report.xlsx",
                    mime=_XLSX_MIME,
                    key="export_dl_dmrb",
                )

        with tab_misc:
            st.caption("Narrative summary and dashboard chart image.")
            c3, c4 = st.columns(2)
            with c3:
                st.download_button(
                    "Download Weekly Summary (TXT)",
                    data=st.session_state.get("weekly_summary_bytes") or b"",
                    file_name="Weekly_Summary.txt",
                    mime="text/plain",
                    key="export_dl_weekly",
                )
            with c4:
                st.download_button(
                    "Download Dashboard Chart (PNG)",
                    data=st.session_state.get("chart_bytes") or b"",
                    file_name="Dashboard_Chart.png",
                    mime="image/png",
                    key="export_dl_chart",
                )

        with tab_zip:
            st.caption("Single archive with all of the above.")
            st.download_button(
                "Download All Reports (ZIP)",
                data=st.session_state.get("zip_bytes") or b"",
                file_name="DMRB_Reports.zip",
                mime="application/zip",
                key="export_dl_zip",
                width="stretch",
            )


def _exports_ready() -> bool:
    return bool(st.session_state.get("final_report_bytes"))


def _export_last_prepare_caption() -> None:
    n = st.session_state.get("export_turnover_count")
    d = st.session_state.get("export_prepared_date")
    if n is None or not d:
        return
    st.caption(f"Last prepare: **{d}** · **{n}** turnover rows in export.")


@st.cache_data(ttl=60)
def _property_name(property_id: int) -> str:
    props = property_service.get_all_properties()
    for p in props:
        if p["property_id"] == property_id:
            return p["name"]
    return f"Property {property_id}"

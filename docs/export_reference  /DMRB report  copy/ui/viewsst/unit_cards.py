import streamlit as st
import pandas as pd
import math

from ui.logic.filters import (
    filter_by_phase,
    filter_by_status,
    filter_by_nvm,
    sort_by_movein_then_dv,
)

from ui.logic.filter_controls import render_filter_controls


REQUIRED_COLUMNS = [
    "Unit", "Status", "DV", "Move_in", "Move_out", "Ready_Date",
    "Attention_Badge", "Status_Norm", "N/V/M", "P",
]

CARDS_PER_PAGE = 20

STATUS_COLORS = {
    "vacant ready": "#28a745",
    "vacant not ready": "#ffc107",
    "on notice": "#17a2b8",
}

TASK_STATUS_DOT = {
    "done": "🟢",
    "in progress": "🟡",
    "pending": "🔴",
    "not started": "⚪",
}

CARD_CSS = """
<style>
.uc-card {
    background: #1e1e2e;
    border: 1px solid #2a2a3d;
    color: #e0e0e0;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 6px;
    font-size: 15px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.15);
    transition: box-shadow 0.15s ease;
}
.uc-card:hover {
    box-shadow: 0 3px 8px rgba(0,0,0,0.25);
}
.uc-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
    padding-bottom: 5px;
    border-bottom: 1px solid #2a2a3d;
}
.uc-unit-name {
    font-weight: 700;
    font-size: 1.15em;
}
.uc-alert {
    font-size: 0.85em;
}
.uc-badge {
    font-size: 0.88em;
    padding: 3px 12px;
    border-radius: 12px;
    font-weight: 600;
    white-space: nowrap;
}
.uc-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 3px 16px;
    font-size: 1em;
}
.uc-field label {
    color: #888;
    font-size: 0.82em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: block;
    margin-bottom: 1px;
}
.uc-field span {
    font-weight: 500;
}
.uc-task-table {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 2px 12px;
    margin-top: 6px;
    padding-top: 5px;
    border-top: 1px solid #2a2a3d;
    font-size: 1em;
    text-align: center;
}
.uc-task-col label {
    color: #888;
    font-size: 0.82em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
    display: block;
    margin-bottom: 2px;
}
.uc-task-col .td-detail {
    color: #ccc;
    font-size: 0.92em;
    white-space: nowrap;
}
.uc-bottom {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 3px 16px;
    margin-top: 6px;
    padding-top: 5px;
    border-top: 1px solid #2a2a3d;
    font-size: 1em;
}
.uc-notes {
    grid-column: span 3;
    color: #aaa;
    font-size: 0.92em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
}
</style>
"""


def _safe(val):
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    s = str(val).strip().lower()
    if s in ("", "none", "nan", "nat", "0"):
        return None
    return val


def _fmt_date(raw):
    v = _safe(raw)
    if v is None:
        return "—"
    try:
        dt = pd.to_datetime(v, errors="coerce")
        if pd.isna(dt):
            return "—"
        return dt.strftime("%m/%d/%Y")
    except Exception:
        return "—"


def _fmt_num(raw):
    v = _safe(raw)
    if v is None:
        return "—"
    try:
        return str(int(float(v)))
    except Exception:
        return str(raw)


def _fmt_val(raw):
    v = _safe(raw)
    return str(v) if v is not None else "—"


def _task_dot(status_val):
    v = _safe(status_val)
    if v is None:
        return "⚪"
    return TASK_STATUS_DOT.get(str(v).strip().lower(), "⚪")


def _field(label, value):
    return f'<div class="uc-field"><label>{label}</label><span>{value}</span></div>'


def _task_col(label, date_val, status_val):
    dot = _task_dot(status_val)
    date = _fmt_date(date_val)
    status_text = _fmt_val(status_val)
    return (
        f'<div class="uc-task-col">'
        f'  <label>{label}</label>'
        f'  <span class="td-detail">{date} - {dot} {status_text}</span>'
        f'</div>'
    )


def _build_card_html(row):
    status_norm = str(row.get("Status_Norm", "")).strip().lower()
    border_color = STATUS_COLORS.get(status_norm, "#555")
    badge_bg = f"{border_color}26"

    unit = row.get("Unit", "")
    status = row.get("Status", "")
    alert_raw = _safe(row.get("Attention_Badge"))
    alert = str(alert_raw) if alert_raw is not None else ""

    notes_raw = _safe(row.get("Notes"))
    notes = str(notes_raw)[:80] if notes_raw is not None else "—"

    return (
        f'<div class="uc-card" style="border-left:4px solid {border_color};">'

        f'  <div class="uc-header">'
        f'    <span class="uc-unit-name">{unit}</span>'
        f'    <span>'
        f'      <span class="uc-badge" style="background:{badge_bg};color:{border_color};">{status}</span>'
        f'      <span class="uc-alert">{alert}</span>'
        f'    </span>'
        f'  </div>'

        f'  <div class="uc-grid">'
        f'    {_field("Move Out", _fmt_date(row.get("Move_out")))}'
        f'    {_field("Ready Date", _fmt_date(row.get("Ready_Date")))}'
        f'    {_field("Days Vacant", _fmt_num(row.get("DV")))}'
        f'    {_field("Move In", _fmt_date(row.get("Move_in")))}'
        f'    {_field("DTBR", _fmt_num(row.get("DTBR")))}'
        f'    {_field("N/V/M", _fmt_val(row.get("N/V/M")))}'
        f'    {_field("Assign", _fmt_val(row.get("Assign")))}'
        f'    {_field("W/D", _fmt_val(row.get("W_D")))}'
        f'  </div>'

        f'  <div class="uc-task-table">'
        f'    {_task_col("Insp", row.get("Insp"), row.get("Insp_status"))}'
        f'    {_task_col("Paint", row.get("Paint"), row.get("Paint_status"))}'
        f'    {_task_col("MR", row.get("MR"), row.get("MR_Status"))}'
        f'    {_task_col("HK", row.get("HK"), row.get("HK_Status"))}'
        f'    {_task_col("CC", row.get("CC"), row.get("CC_status"))}'
        f'  </div>'

        f'  <div class="uc-bottom">'
        f'    {_field("QC", _fmt_val(row.get("QC")))}'
        f'    {_field("Phase", _fmt_num(row.get("P")))}'
        f'    {_field("Building", _fmt_val(row.get("B")))}'
        f'    {_field("Unit", _fmt_num(row.get("U")))}'
        f'    <div></div>'
        f'    <div class="uc-notes" title="{notes}">Notes: {notes}</div>'
        f'  </div>'

        f'</div>'
    )


def render(df: pd.DataFrame):

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        st.error(f"Missing required columns: {missing}")
        return

    st.title("Unit Cards")

    st.caption(
        "Visual unit board. Cards are color-coded by status "
        "and sorted by move-in urgency."
    )

    st.markdown(CARD_CSS, unsafe_allow_html=True)

    selected_phase, selected_status, selected_nvm = \
        render_filter_controls(df, key_prefix="uc")

    filtered = df.copy()
    filtered = filter_by_phase(filtered, selected_phase)
    filtered = filter_by_status(filtered, selected_status)
    filtered = filter_by_nvm(filtered, selected_nvm)
    filtered = sort_by_movein_then_dv(filtered)

    total = len(filtered)
    vacant_ready = int((filtered["Status_Norm"] == "vacant ready").sum())
    vacant_not_ready = int((filtered["Status_Norm"] == "vacant not ready").sum())
    on_notice = int((filtered["Status_Norm"] == "on notice").sum())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Units", total)
    m2.metric("Vacant Ready", vacant_ready)
    m3.metric("Vacant Not Ready", vacant_not_ready)
    m4.metric("On Notice", on_notice)

    total_pages = max(1, math.ceil(total / CARDS_PER_PAGE))

    page = st.number_input(
        "Page",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1,
        key="uc_page",
    )

    start = (page - 1) * CARDS_PER_PAGE
    end = start + CARDS_PER_PAGE
    page_df = filtered.iloc[start:end]

    cards_html = "".join(_build_card_html(row) for _, row in page_df.iterrows())

    st.markdown(cards_html, unsafe_allow_html=True)

    st.caption(f"Showing {start + 1}–{min(end, total)} of {total} units")

"""
Page 6 — Turnover Detail (skeleton).
Full replica of the real screen: unit lookup, then all panels with same layout,
dropdowns (Status, W/D, Execution, Confirm, Assignee, Blocking), Authority expander, Tasks table, Notes.
Uses same options as ui.state.constants. Placeholder data only; no backend.
Run standalone: streamlit run docs/skeleton_pages/page_06_turnover_detail.py
"""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

# ---------------------------------------------------------------------------
# Same options as ui.state.constants (so dropdowns match the real page)
# ---------------------------------------------------------------------------
STATUS_OPTIONS = ["Vacant ready", "Vacant not ready", "On notice"]
ASSIGNEE_OPTIONS = ["", "Michael", "Brad", "Miguel A", "Roadrunner", "Make Ready Co"]
BLOCK_OPTIONS = ["Not Blocking", "Key Delivery", "Vendor Delay", "Parts on Order", "Permit Required", "Other"]
DEFAULT_TASK_OFFSETS = {
    "Insp": 1, "CB": 2, "MRB": 3, "Paint": 4, "MR": 5, "HK": 6, "CC": 7, "FW": 8, "QC": 9,
}
TASK_TYPES_ALL = ["Insp", "CB", "MRB", "Paint", "MR", "HK", "CC", "FW", "QC"]
TASK_DISPLAY_NAMES = {
    "Insp": "Inspection",
    "CB": "Carpet Bid",
    "MRB": "Make Ready Bid",
    "Paint": "Paint",
    "MR": "Make Ready",
    "HK": "Housekeeping",
    "CC": "Carpet Clean",
    "FW": "Final Walk",
    "QC": "Quality Control",
}
EXEC_LABELS = ["", "Not Started", "Scheduled", "In Progress", "Done", "N/A", "Canceled"]
EXEC_VALUE_TO_LABEL = {
    None: "", "NOT_STARTED": "Not Started", "SCHEDULED": "Scheduled",
    "IN_PROGRESS": "In Progress", "VENDOR_COMPLETED": "Done", "NA": "N/A", "CANCELED": "Canceled",
}
CONFIRM_LABELS = ["Pending", "Confirmed", "Rejected", "Waived"]
CONFIRM_VALUE_TO_LABEL = {"PENDING": "Pending", "CONFIRMED": "Confirmed", "REJECTED": "Rejected", "WAIVED": "Waived"}
WD_OPTS = ["No", "Yes", "Yes stack"]

# Placeholder dropdown_config (task_assignees per type, task_offsets)
def _placeholder_dropdown_config():
    return {
        "task_assignees": {
            "Insp": {"options": ["Michael", "Miguel A"], "default": "Michael"},
            "CB": {"options": ["Make Ready Co"], "default": ""},
            "MRB": {"options": ["Make Ready Co"], "default": "Make Ready Co"},
            "Paint": {"options": ["Roadrunner"], "default": "Roadrunner"},
            "MR": {"options": ["Make Ready Co"], "default": "Make Ready Co"},
            "HK": {"options": ["Brad"], "default": "Brad"},
            "CC": {"options": ["Brad"], "default": ""},
            "FW": {"options": ["Michael", "Miguel A"], "default": ""},
            "QC": {"options": ["Michael", "Miguel A", "Brad"], "default": "Michael"},
        },
        "task_offsets": dict(DEFAULT_TASK_OFFSETS),
    }


def _safe_index(opts: list, value: str) -> int:
    try:
        return opts.index(value) if value in opts else 0
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# Placeholder: unit selected? and full detail payload
# ---------------------------------------------------------------------------
def _placeholder_unit_selected() -> bool:
    return st.session_state.get("sk_detail_unit_selected", False)


def _placeholder_detail():
    """One turnover with all fields needed for panels; tasks list has one per task type."""
    move_out = date(2025, 3, 1)
    cfg = _placeholder_dropdown_config()
    tasks = []
    for task_type in TASK_TYPES_ALL:
        offset = cfg["task_offsets"].get(task_type, 1)
        tasks.append({
            "task_id": hash(task_type) % 100000,
            "task_type": task_type,
            "display_name": TASK_DISPLAY_NAMES.get(task_type, task_type),
            "assignee": cfg["task_assignees"].get(task_type, {}).get("default", ""),
            "vendor_due_date": move_out + timedelta(days=offset),
            "execution_status": "IN_PROGRESS" if task_type == "Insp" else "NOT_STARTED",
            "confirmation_status": "CONFIRMED" if task_type == "QC" else "PENDING",
            "required": True,
            "blocking": False,
            "blocking_reason": "Not Blocking",
        })
    return {
        "unit_code": "5-1-101",
        "phase_display": "5",
        "building": "1",
        "unit_number": "101",
        "nvm": "Vacant",
        "assign_display": "Michael",
        "legal_confirmed": True,
        "status": "Vacant not ready",
        "move_out": move_out,
        "dv": 12,
        "ready_date": date(2025, 3, 15),
        "move_in": date(2025, 3, 20),
        "dtbr": 7,
        "wd_present": True,
        "wd_present_type": "Yes",
        "wd_notified": False,
        "wd_installed": True,
        "risks": [
            {"severity": "CRITICAL", "risk_type": "SLA", "description": "Past due"},
        ],
        "turnover": {
            "move_out_date": move_out.isoformat(),
            "report_ready_date": "2025-03-15",
            "move_in_date": "2025-03-20",
            "manual_ready_status": "Vacant not ready",
            "last_import_move_out_date": "2025-03-01",
            "last_import_ready_date": "2025-03-14",
            "last_import_move_in_date": "2025-03-20",
            "last_import_status": "Vacant not ready",
            "move_out_manual_override_at": None,
            "ready_manual_override_at": "2025-03-10T12:00:00",
            "move_in_manual_override_at": None,
            "status_manual_override_at": None,
            "legal_confirmation_source": True,
        },
        "tasks": tasks,
        "notes": [
            {"note_id": 1, "description": "Follow up on carpet", "note_type": "info", "blocking": False, "resolved_at": None},
        ],
    }


def _fmt_date(val) -> str:
    if val is None or val == "":
        return "—"
    if hasattr(val, "isoformat"):
        return val.strftime("%m/%d/%Y")
    s = str(val)
    if len(s) >= 10:
        return s[:10].replace("-", "/")
    return s


def render() -> None:
    st.caption("Active Property: **Sample Property**")

    # ---------- Unit lookup state ----------
    if not _placeholder_unit_selected():
        st.subheader("Turnover Detail")
        unit_search = st.text_input("Unit code", key="detail_unit_search")
        if st.button("Go", key="sk_detail_go"):
            if (unit_search or "").strip():
                st.session_state.sk_detail_unit_selected = True
                st.rerun()
            else:
                st.warning("Unit not found")
        return

    d = _placeholder_detail()
    t = d["turnover"]
    tasks_for_turnover = d["tasks"]
    notes_for_turnover = d["notes"]
    risks_for_turnover = d["risks"]
    detail_move_out = d["move_out"]
    _detail_writes = True  # skeleton: allow edits

    # ---------- Panel A: UNIT INFORMATION ----------
    with st.container(border=True):
        st.markdown("**UNIT INFORMATION**")
        hdr_left, hdr_right = st.columns([4, 1])
        with hdr_left:
            legal_src = d["legal_confirmed"]
            legal_dot_html = (
                '<span title="Legal move-out confirmed" style="color:#28a745;font-size:1.1em;">●</span>'
                if legal_src
                else '<span title="No legal confirmation" style="color:#dc3545;font-size:1.1em;">●</span>'
            )
            unit_label = f"Unit {d['unit_code']}"
            st.markdown(f"<h3 style='margin:0;'>{unit_label} {legal_dot_html}</h3>", unsafe_allow_html=True)
        with hdr_right:
            if st.button("← Back", key="sk_detail_back"):
                st.session_state.sk_detail_unit_selected = False
                st.rerun()
        id1, id2, id3, id4, id5 = st.columns([0.8, 0.8, 0.8, 0.8, 1.2])
        id1.write(f"**Phase:** {d['phase_display']}")
        id2.write(f"**Building:** {d['building']}" if d["building"] else "**Building:** —")
        id3.write(f"**Unit:** {d['unit_number']}")
        id4.write(f"**N/V/M:** {d['nvm']}")
        id5.write(f"**Assignee:** {d['assign_display']}")

    # ---------- Panel B: STATUS & QC ----------
    with st.container(border=True):
        s1, s2 = st.columns([2, 1])
        with s1:
            cur_status = d["status"]
            idx = _safe_index(STATUS_OPTIONS, cur_status)
            st.selectbox(
                "Status",
                STATUS_OPTIONS,
                index=idx,
                key="detail_status",
                disabled=not _detail_writes,
            )
        with s2:
            st.write("")
            st.button(
                "✅ Confirm Quality Control",
                type="primary",
                use_container_width=True,
                key="detail_confirm_qc",
                disabled=not _detail_writes,
            )

    # ---------- Panel C: DATES ----------
    with st.container(border=True):
        st.markdown("**DATES**")
        dt1, dt2, dt3, dt4, dt5 = st.columns([1.2, 0.6, 1.2, 1.2, 0.6])
        with dt1:
            st.date_input(
                "Move-Out",
                value=d["move_out"],
                key="detail_mo",
                format="MM/DD/YYYY",
                disabled=not _detail_writes,
            )
        if d["dv"] is not None and d["dv"] > 10:
            dt2.markdown(f'**DV**<br><span style="color:#dc3545;font-weight:bold">{d["dv"]}</span>', unsafe_allow_html=True)
        else:
            dt2.write(f"**DV:** {d['dv'] if d['dv'] is not None else '—'}")
        with dt3:
            st.date_input(
                "Ready Date",
                value=d["ready_date"],
                key="detail_rr",
                format="MM/DD/YYYY",
                disabled=not _detail_writes,
            )
        with dt4:
            st.date_input(
                "Move-In",
                value=d["move_in"],
                key="detail_mi",
                format="MM/DD/YYYY",
                disabled=not _detail_writes,
            )
        dt5.write(f"**DTBR:** {d['dtbr'] if d['dtbr'] is not None else '—'}")

    # ---------- Panel D: W/D STATUS ----------
    with st.container(border=True):
        st.markdown("**W/D STATUS**")
        w1, w2, w3 = st.columns(3)
        with w1:
            cur_wd = (d.get("wd_present_type") or "Yes") if d.get("wd_present") else "No"
            wd_idx = _safe_index(WD_OPTS, cur_wd)
            st.selectbox(
                "Present",
                WD_OPTS,
                index=wd_idx,
                key="detail_wd_present",
                disabled=not _detail_writes,
            )
        with w2:
            st.write("")
            notified = "✅ Yes" if d.get("wd_notified") else "No"
            st.markdown(f'<p style="text-align:left;"><strong>Notified:</strong> {notified}</p>', unsafe_allow_html=True)
            if not d.get("wd_notified"):
                st.button("Mark Notified", key="detail_wd_notified", disabled=not _detail_writes)
        with w3:
            st.write("")
            installed = "✅ Yes" if d.get("wd_installed") else "No"
            st.markdown(f'<p style="text-align:left;"><strong>Installed:</strong> {installed}</p>', unsafe_allow_html=True)
            if not d.get("wd_installed"):
                st.button("Mark Installed", key="detail_wd_installed", disabled=not _detail_writes)

    # ---------- Panel E: RISKS ----------
    with st.container(border=True):
        st.markdown('<p style="text-align:left;"><strong>RISKS</strong></p>', unsafe_allow_html=True)
        if risks_for_turnover:
            for r in risks_for_turnover:
                sev = r.get("severity", "")
                icon = "🔴" if sev == "CRITICAL" else "🟡" if sev == "WARNING" else "⚪"
                st.markdown(
                    f'<p style="text-align:left;">{icon} {r.get("risk_type", "")} ({sev}) — {r.get("description", "") or ""}</p>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No active risks")

    # ---------- Panel E2: AUTHORITY & IMPORT COMPARISON ----------
    _override_fields = [
        ("Move-Out Date", "move_out_date", "last_import_move_out_date", "move_out_manual_override_at"),
        ("Ready Date", "report_ready_date", "last_import_ready_date", "ready_manual_override_at"),
        ("Move-In Date", "move_in_date", "last_import_move_in_date", "move_in_manual_override_at"),
        ("Status", "manual_ready_status", "last_import_status", "status_manual_override_at"),
    ]
    auth_rows = []
    for label, sys_key, import_key, override_key in _override_fields:
        sys_val = t.get(sys_key) or ""
        sys_val = _fmt_date(sys_val) if sys_key != "manual_ready_status" else (sys_val or "—")
        import_val = t.get(import_key) or ""
        import_val = _fmt_date(import_val) if import_key != "last_import_status" else (import_val or "—")
        override_active = t.get(override_key) is not None
        legal_src = t.get("legal_confirmation_source")
        if sys_key == "move_out_date" and legal_src:
            source = "Legal Confirmed"
        elif override_active:
            source = "Manual"
        else:
            source = "Import"
        override_display = "Active" if override_active else ""
        _divergent = (
            override_active
            and str(t.get(sys_key) or "") != str(t.get(import_key) or "")
            and t.get(import_key) is not None
        )
        _pending_clear = (
            override_active
            and str(t.get(sys_key) or "") == str(t.get(import_key) or "")
            and t.get(import_key) is not None
        )
        auth_rows.append({
            "Field": label,
            "Current (System)": sys_val,
            "Last Import": import_val,
            "Source": source,
            "Override": override_display,
            "_override_active": override_active,
            "_divergent": _divergent,
            "_pending_clear": _pending_clear,
            "_override_key": override_key,
        })
    _any_override = any(ar["_override_active"] for ar in auth_rows)
    _any_divergence = any(ar["_divergent"] for ar in auth_rows)
    _panel_indicator = " ⚠" if (_any_override or _any_divergence) else ""

    with st.expander(f"▶ Authority & Import Comparison{_panel_indicator}", expanded=False):
        for i, ar in enumerate(auth_rows):
            cols = st.columns([1.5, 1.5, 1.5, 1, 0.8, 0.8])
            if i == 0:
                cols[0].markdown("**Field**")
                cols[1].markdown("**Current (System)**")
                cols[2].markdown("**Last Import**")
                cols[3].markdown("**Source**")
                cols[4].markdown("**Override**")
                cols[5].markdown("")
                cols = st.columns([1.5, 1.5, 1.5, 1, 0.8, 0.8])
            if ar["_divergent"]:
                cols[0].markdown(
                    f'<span style="background-color:rgba(255,193,7,0.2);padding:2px 4px;border-radius:3px;">{ar["Field"]}</span>',
                    unsafe_allow_html=True,
                )
            else:
                cols[0].write(ar["Field"])
            cols[1].write(ar["Current (System)"])
            cols[2].write(ar["Last Import"])
            cols[3].write(ar["Source"])
            if ar["_pending_clear"]:
                cols[4].caption("Pending Clear")
            else:
                cols[4].write(ar["Override"])
            if ar["_override_active"]:
                if cols[5].button("Clear", key=f"clear_override_{ar['_override_key']}"):
                    pass  # skeleton: no backend

    # ---------- Panel F: TASKS (all 9 task types, same columns as real page) ----------
    task_assignees_cfg = _placeholder_dropdown_config().get("task_assignees", {})
    detail_offsets_cfg = _placeholder_dropdown_config().get("task_offsets", DEFAULT_TASK_OFFSETS)
    tasks_sorted = sorted(tasks_for_turnover, key=lambda x: (x.get("task_type", ""), x.get("task_id", 0)))

    with st.container(border=True):
        st.markdown("**TASKS**")
        th1, th2, th3, th4, th5, th6, th7 = st.columns([1.0, 1.2, 1.0, 1.2, 1.0, 0.5, 1.2])
        th1.markdown("**Task**")
        th2.markdown("**Assignee**")
        th3.markdown("**Date**")
        th4.markdown("**Execution**")
        th5.markdown("**Confirm**")
        th6.markdown("**Req**")
        th7.markdown("**Blocking**")
        st.divider()

        for task in tasks_sorted:
            task_type = task.get("task_type", "")
            task_id = task.get("task_id")
            if not task_id:
                continue
            display_name = TASK_DISPLAY_NAMES.get(task_type, task_type)
            due_val = task.get("vendor_due_date") or (detail_move_out + timedelta(days=detail_offsets_cfg.get(task_type, 1)))
            exec_cur = (task.get("execution_status") or "NOT_STARTED").upper()
            exec_label = EXEC_VALUE_TO_LABEL.get(exec_cur, "Not Started")
            exec_options = [l for l in EXEC_LABELS if l]
            if exec_label and exec_label not in exec_options:
                exec_options.append(exec_label)
            exec_idx = _safe_index(exec_options, exec_label)
            conf_cur = (task.get("confirmation_status") or "PENDING").upper()
            conf_label = CONFIRM_VALUE_TO_LABEL.get(conf_cur, "Pending")
            conf_options = list(CONFIRM_LABELS)
            if conf_label and conf_label not in conf_options:
                conf_options.append(conf_label)
            conf_idx = _safe_index(conf_options, conf_label)
            cfg = task_assignees_cfg.get(task_type, {})
            cfg_opts = cfg.get("options") or [o for o in ASSIGNEE_OPTIONS if o]
            assignee_opts = ("",) + tuple(sorted({x for x in cfg_opts if x}))
            db_assignee = (task.get("assignee") or "").strip()
            if db_assignee and db_assignee not in assignee_opts:
                assignee_opts = assignee_opts + (db_assignee,)
            assignee_key = f"detail_assignee_{task_id}_{task_type}"
            cur_block = task.get("blocking_reason") or "Not Blocking"
            block_options = list(BLOCK_OPTIONS)
            if cur_block and cur_block not in block_options:
                block_options.append(cur_block)
            block_idx = _safe_index(block_options, cur_block)

            tc1, tc2, tc3, tc4, tc5, tc6, tc7 = st.columns([1.0, 1.2, 1.0, 1.2, 1.0, 0.5, 1.2])
            tc1.write(display_name)
            with tc2:
                st.selectbox(
                    "Assignee",
                    assignee_opts,
                    index=_safe_index(assignee_opts, db_assignee) if db_assignee in assignee_opts else 0,
                    key=assignee_key,
                    label_visibility="collapsed",
                    disabled=not _detail_writes,
                )
            with tc3:
                st.date_input(
                    "Date",
                    value=due_val,
                    key=f"detail_due_{task_id}_{task_type}",
                    label_visibility="collapsed",
                    format="MM/DD/YYYY",
                    disabled=not _detail_writes,
                )
            with tc4:
                st.selectbox(
                    "Exec",
                    exec_options,
                    index=exec_idx,
                    key=f"detail_exec_{task_id}_{task_type}",
                    label_visibility="collapsed",
                    disabled=not _detail_writes,
                )
            with tc5:
                st.selectbox(
                    "Confirm",
                    conf_options,
                    index=conf_idx,
                    key=f"detail_conf_{task_id}_{task_type}",
                    label_visibility="collapsed",
                    disabled=not _detail_writes,
                )
            with tc6:
                st.checkbox(
                    "Req",
                    value=bool(task.get("required")),
                    key=f"detail_req_{task_id}_{task_type}",
                    label_visibility="collapsed",
                    disabled=not _detail_writes,
                )
            with tc7:
                st.selectbox(
                    "Block",
                    block_options,
                    index=block_idx,
                    key=f"detail_block_{task_id}_{task_type}",
                    label_visibility="collapsed",
                    disabled=not _detail_writes,
                )

    # ---------- Panel G: NOTES ----------
    with st.container(border=True):
        st.markdown("**NOTES**")
        for n in notes_for_turnover:
            col1, col2 = st.columns([4, 1])
            severity = n.get("note_type", "info")
            icon = "⛔" if n.get("blocking") else ""
            with col1:
                st.write(f"- {icon} {(n.get('description') or '')} ({severity})")
            with col2:
                if n.get("resolved_at"):
                    st.caption("Resolved")
                else:
                    st.button("Resolve", key=f"note_resolve_{n.get('note_id')}")
        st.text_area("Add note (free text)", key="detail_new_note", placeholder="Description...")
        st.button("Add note", key="detail_add_note")


if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Turnover Detail (skeleton)")
    render()

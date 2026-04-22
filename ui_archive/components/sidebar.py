import streamlit as st
from services import board_service, property_service, scope_service


# Sidebar expander groups: (group_label, expanded, [(label, page_key), ...])
_NAV_GROUPS = [
    ("Quick Tools", True, [
        ("➕ Add Turnover", "add_turnover"),
        ("🔍 Unit Lookup", "unit_detail"),
        ("🤖 DMRB AI Agent", "ai_agent"),
    ]),
    ("Daily Ops", True, [
        ("🌅 Morning WF", "morning_workflow"),
        ("📋 DMRB Board", "board"),
        ("📅 Ops Schedule", "operations_schedule"),
        ("🚩 Flag Bridge", "flag_bridge"),
        ("📡 Risk Radar", "risk_radar"),
        ("🔧 W/O Validator", "work_order_validator"),
    ]),
    ("Import & Reports", True, [
        ("📥 Import Reports", "import_console"),
        ("🛠 Repair Reports", "repair_reports"),
        ("Export Reports", "export_reports"),
    ]),
    ("Administration", False, [
        ("📥 Report Operations", "import_reports"),
        ("🏗️ Structure", "property_structure"),
        ("⚙️ Admin", "admin"),
    ]),
]

# Flag categories for the Top Flags expanders
_FLAG_CATEGORIES = [
    ("INSPECTION_BREACH", "📋 Insp Breach"),
    ("SLA_BREACH", "⚠ SLA Breach"),
    ("MOVE_IN_DANGER", "🔴 MI Danger"),
    ("PLAN_BLOCKED", "📅 Plan Breach"),
]



def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            "<h2 style='margin-top:-1rem;margin-bottom:0'>The DMRB</h2>"
            "<p style='margin:0 0 .5rem;font-size:.85rem;color:grey'>"
            "Apartment Turn Tracker</p>",
            unsafe_allow_html=True,
        )

        validator_only = st.session_state.get("access_mode") == "validator_only"

        # ── Property selector ────────────────────────────────────────────
        properties = property_service.get_all_properties()
        if properties:
            names = [p["name"] for p in properties]
            ids = [p["property_id"] for p in properties]

            current_id = st.session_state.get("property_id")
            default_index = ids.index(current_id) if current_id in ids else 0

            selected_name = st.selectbox(
                "Property",
                options=names,
                index=default_index,
            )
            st.session_state.property_id = ids[names.index(selected_name)]
        else:
            if validator_only:
                st.info("No properties are available. Contact an administrator to add one.")
            else:
                st.info("No properties yet — go to **Admin** to create one.")

        st.divider()

        # ── Navigation ───────────────────────────────────────────────────
        current_page = st.session_state.get("current_page", "board")

        if validator_only:
            st.caption("Access: Work Order Validator only")
            page_key = "work_order_validator"
            label = "🔧 W/O Validator"
            is_active = page_key == current_page
            if st.button(
                label,
                key=f"nav_btn_{page_key}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                if page_key != current_page:
                    st.session_state.current_page = page_key
                    st.rerun()
        else:
            for group_label, expanded, items in _NAV_GROUPS:
                with st.expander(group_label, expanded=expanded):
                    for label, page_key in items:
                        is_active = page_key == current_page
                        if st.button(
                            label,
                            key=f"nav_btn_{page_key}",
                            type="primary" if is_active else "secondary",
                            use_container_width=True,
                        ):
                            if page_key != current_page:
                                prev_page = current_page
                                st.session_state.current_page = page_key
                                if page_key == "unit_detail" and prev_page != "unit_detail":
                                    st.session_state.pop("selected_turnover_id", None)
                                st.rerun()

            # ── Top Flags ────────────────────────────────────────────────
            property_id = st.session_state.get("property_id")
            if property_id is not None:
                st.divider()
                _render_top_flags(property_id)


def _load_flag_units(property_id: int) -> dict[str, list[dict]]:
    uid = int(st.session_state.get("user_id") or 0)
    phase_scope = scope_service.get_phase_scope(uid, property_id)
    return board_service.get_flag_units(property_id, phase_scope=phase_scope, user_id=uid)


def _render_top_flags(property_id: int) -> None:
    st.markdown("**Top Flags**")

    flag_units = _load_flag_units(property_id)
    any_flags = any(units for units in flag_units.values())

    if not any_flags:
        st.caption("No flagged units")
        return

    for i, (cat_key, cat_label) in enumerate(_FLAG_CATEGORIES):
        units = flag_units.get(cat_key, [])
        title = f"{cat_label} ({len(units)})"
        with st.expander(title):
            if not units:
                st.caption("—")
            else:
                for j, entry in enumerate(units[:5]):
                    label = f"{entry['unit_code']} · DV {entry['dv']}"
                    if st.button(label, key=f"sb_flag_{i}_{j}"):
                        st.session_state.selected_turnover_id = entry["turnover_id"]
                        st.session_state.current_page = "unit_detail"
                        st.rerun()

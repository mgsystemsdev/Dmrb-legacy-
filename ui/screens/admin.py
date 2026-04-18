"""Admin screen — control bar, four tabs.

Control bar: DB Writes toggle, Active Property display, New Property creation.
Tabs: Add Turnover, Unit Master Import, Phase Manager, App users.
"""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from services import (
    app_user_service,
    property_service,
    scope_service,
    system_settings_service,
    turnover_service,
    unit_service,
)
from services.app_user_service import AppUserError
from services.turnover_service import TurnoverError
from services.write_guard import WritesDisabledError


def render_admin() -> None:
    st.subheader("Admin")

    property_id = st.session_state.get("property_id")

    # ── Control bar ──────────────────────────────────────────────────────
    # Sync checkbox from persistent DB setting (source of truth)
    st.session_state.admin_enable_db_writes = system_settings_service.get_enable_db_write()

    def _on_db_writes_change():
        system_settings_service.set_enable_db_write(st.session_state.admin_enable_db_writes)

    with st.container(border=True):
        ac1, ac2, ac3 = st.columns([1.2, 1.6, 1.6])
        with ac1:
            st.checkbox(
                "Enable DB Writes",
                key="admin_enable_db_writes",
                on_change=_on_db_writes_change,
            )
        with ac2:
            if property_id is not None:
                st.write(f"**Active Property:** {_property_name(property_id)}")
            else:
                st.write("**Active Property:** —")
        with ac3:
            new_name = st.text_input(
                "New Property", value="", key="admin_new_property",
                placeholder="Property name",
            )
            if st.button("Create Property", key="admin_create_property"):
                name = new_name.strip()
                if name:
                    try:
                        prop = property_service.create_property(name)
                        st.session_state.property_id = prop["property_id"]
                        st.cache_data.clear()
                        st.success(f"Property **{name}** created.")
                        st.rerun()
                    except WritesDisabledError as exc:
                        st.warning(str(exc))
                else:
                    st.warning("Enter a property name.")

    db_on = system_settings_service.get_enable_db_write()
    if not db_on:
        st.caption("DB writes are **off**. You can browse and export; turn this on to save changes.")
    if property_id is not None:
        st.caption(f"Active Property: **{_property_name(property_id)}**")

    # ── Tabs ─────────────────────────────────────────────────────────────
    tab_add, tab_unit_master, tab_phases, tab_app_users = st.tabs(
        [
            "Add Turnover",
            "Unit Master Import",
            "Phase Manager",
            "App users",
        ]
    )

    with tab_add:
        _render_add_turnover(property_id)

    with tab_unit_master:
        _render_unit_master(property_id)

    with tab_phases:
        _render_phase_manager(property_id)

    with tab_app_users:
        _render_app_users()


@st.cache_data(ttl=60)
def _cached_list_unit_master_import_units(property_id: int) -> list[dict]:
    return unit_service.list_unit_master_import_units(property_id)




# ── Tab: Add Turnover ────────────────────────────────────────────────────────

def _render_add_turnover(property_id: int | None) -> None:
    with st.container(border=True):
        st.markdown("**ADD TURNOVER**")
        st.caption(
            "Add unit to active turnover. Unit must already exist in the database; "
            "one open turnover per unit."
        )
        if property_id is None:
            st.info("Select a property first.")
            return

        phases = property_service.get_phases(property_id)
        if not phases:
            st.info("No phases configured for this property.")
            return

        c1, c2, c3 = st.columns(3)
        with c1:
            phase_labels = [p.get("name") or p["phase_code"] for p in phases]
            phase_idx = st.selectbox(
                "Phase", range(len(phases)),
                format_func=lambda i: phase_labels[i],
                key="admin_add_phase",
            )
        selected_phase = phases[phase_idx]

        buildings = property_service.get_buildings(selected_phase["phase_id"])
        if not buildings:
            st.info("No buildings in the selected phase.")
            return

        with c2:
            building_labels = [b.get("name") or b["building_code"] for b in buildings]
            building_idx = st.selectbox(
                "Building", range(len(buildings)),
                format_func=lambda i: building_labels[i],
                key="admin_add_building",
            )
        selected_building = buildings[building_idx]

        units = property_service.get_units_by_building(
            property_id, selected_building["building_id"],
        )
        if not units:
            st.info("No active units in the selected building.")
            return

        with c3:
            unit_labels = [u["unit_code_norm"] for u in units]
            unit_idx = st.selectbox(
                "Unit", range(len(units)),
                format_func=lambda i: unit_labels[i],
                key="admin_add_unit",
            )
        selected_unit = units[unit_idx]

    with st.container(border=True):
        st.markdown("**DATES**")
        with st.form(key="admin_add_turnover_form"):
            d1, d2, d3 = st.columns(3)
            with d1:
                move_out = st.date_input("Move-out Date", key="admin_add_mo")
            with d2:
                ready = st.date_input("Ready date (optional)", value=None, key="admin_add_ready")
            with d3:
                move_in = st.date_input("Move-in (optional)", value=None, key="admin_add_mi")
            submitted = st.form_submit_button("Add Turnover", width="stretch")

        if submitted:
            try:
                new = turnover_service.create_turnover(
                    property_id,
                    selected_unit["unit_id"],
                    move_out,
                    move_in_date=move_in,
                    actor="manager",
                )
                st.success(
                    f"Turnover #{new['turnover_id']} created for "
                    f"**{selected_unit['unit_code_norm']}**."
                )
                st.cache_data.clear()
                st.rerun()
            except TurnoverError as exc:
                st.warning(str(exc))
            except WritesDisabledError as exc:
                st.warning(str(exc))


# ── Tab: Unit Master Import ──────────────────────────────────────────────────

def _run_unit_master_import(property_id: int) -> None:
    """Process the uploaded Units.csv and create units/phases/buildings via unit_service."""
    uploaded = st.session_state.get("admin_um_file")
    if uploaded is None:
        st.warning("Upload a CSV file first.")
        return

    try:
        raw_bytes = uploaded.getvalue()
        df = _normalize_unit_columns(_read_csv_flexible(raw_bytes))
    except Exception as exc:
        st.error(f"Failed to parse CSV: {exc}")
        return

    if "unit_code" not in df.columns:
        st.error(
            "CSV must contain a `unit_code` column. "
            f"Found columns: {', '.join(df.columns.tolist())}"
        )
        return

    strict = st.session_state.get("admin_um_strict", False)
    try:
        result = unit_service.import_unit_master(property_id, df, strict)
    except WritesDisabledError as exc:
        st.warning(str(exc))
        return

    created = result["created"]
    skipped = result["skipped"]
    errors = result["errors"]

    parts = [f"**Created:** {created}", f"**Skipped (existing):** {skipped}"]
    if errors:
        parts.append(f"**Errors:** {len(errors)}")
    st.success(" · ".join(parts))
    for err in errors:
        st.warning(err)
    if created:
        st.cache_data.clear()
        st.rerun()


def _render_unit_master(property_id: int | None) -> None:
    with st.container(border=True):
        st.markdown("**UNIT MASTER IMPORT**")
        st.caption(
            "One-time structural bootstrap from Units.csv. "
            "Writes only to unit (and phase/building when creating units)."
        )
        if property_id is None:
            st.info("Select a property first.")
            return

        uc1, uc2, uc3 = st.columns([1, 2, 1])
        with uc1:
            st.checkbox(
                "Strict mode", value=False, key="admin_um_strict",
                help="Fail if unit not found; no creates",
            )
        with uc2:
            st.file_uploader("Units.csv", type=["csv"], key="admin_um_file")
        with uc3:
            st.write("")
            if st.button(
                "Run Unit Master Import", key="admin_um_run",
                width="stretch",
            ):
                _run_unit_master_import(property_id)

    with st.container(border=True):
        st.markdown("**IMPORTED UNITS**")
        imported_units = _cached_list_unit_master_import_units(property_id)
        if imported_units:
            df = pd.DataFrame(imported_units)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("No units imported yet.")


# ── Tab: Phase Manager ────────────────────────────────────────────────────────

def _render_phase_manager(property_id: int | None) -> None:
    with st.container(border=True):
        st.markdown("**PHASE SCOPE**")
        st.caption(
            "Select which phases are visible across the entire app. "
            "Unselected phases are hidden from the board, operations schedule, "
            "and all other screens. Saved to the database."
        )
        if property_id is None:
            st.info("Select a property first.")
            return

        phases = property_service.get_phases(property_id)
        if not phases:
            st.info("No phases found. Import data to create phases automatically.")
            return

        phase_codes = [p["phase_code"] for p in phases]
        phase_id_by_code = {p["phase_code"]: p["phase_id"] for p in phases}
        current_phase_ids = scope_service.get_phase_scope(property_id)
        default_codes = [
            p["phase_code"] for p in phases
            if p["phase_id"] in current_phase_ids
        ]
        if not current_phase_ids or set(current_phase_ids) == {p["phase_id"] for p in phases}:
            default_codes = phase_codes

        selected_codes = st.multiselect(
            "Active Phases",
            options=phase_codes,
            default=default_codes,
            key="admin_phase_select",
        )

        if st.button("Apply Phase Scope", key="admin_phase_apply", width="stretch"):
            try:
                selected_ids = [phase_id_by_code[c] for c in selected_codes if c in phase_id_by_code]
                scope_service.update_phase_scope(property_id, selected_ids)
                st.cache_data.clear()
                st.success(
                    f"Scope saved: **{', '.join(selected_codes)}**"
                    if selected_codes else "Scope saved: **all phases**."
                )
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    with st.container(border=True):
        st.markdown("**PHASES IN DATABASE**")
        current_phase_ids_set = set(scope_service.get_phase_scope(property_id))
        phase_data = []
        for p in phases:
            unit_count = len(property_service.get_units_by_phase(property_id, p["phase_id"]))
            building_count = len(property_service.get_buildings(p["phase_id"]))
            all_phases = {x["phase_id"] for x in phases}
            active = "✅" if (not current_phase_ids_set or current_phase_ids_set == all_phases or p["phase_id"] in current_phase_ids_set) else "—"
            phase_data.append({
                "Phase": p["phase_code"],
                "Active": active,
                "Buildings": building_count,
                "Units": unit_count,
            })
        st.dataframe(pd.DataFrame(phase_data), use_container_width=True, hide_index=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _read_csv_flexible(raw_bytes: bytes) -> pd.DataFrame:
    """Parse a CSV that may have junk/header rows before the real data.

    Strategy: try plain parse first; on failure, scan for the first line
    with multiple comma-separated fields and use it as the header.
    """
    try:
        return pd.read_csv(io.BytesIO(raw_bytes), dtype=str)
    except Exception:
        pass

    lines = raw_bytes.decode("utf-8", errors="replace").splitlines()
    header_idx = 0
    for i, line in enumerate(lines):
        if line.count(",") >= 1:
            header_idx = i
            break

    return pd.read_csv(io.BytesIO(raw_bytes), skiprows=header_idx, dtype=str)


# Column names the CSV might use instead of "unit_code"
_UNIT_CODE_ALIASES = {"Unit", "unit", "Unit Number", "unit_number", "UnitCode", "Unit Code"}


def _normalize_unit_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename known aliases to the canonical ``unit_code`` column name."""
    for alias in _UNIT_CODE_ALIASES:
        if alias in df.columns and "unit_code" not in df.columns:
            df = df.rename(columns={alias: "unit_code"})
            break
    return df


def _render_app_users() -> None:
    """Manage ``app_user`` rows (passwords hashed with Argon2). Used when ``LEGACY_AUTH_SOURCE=db``."""
    flash = st.session_state.pop("_admin_app_user_flash", None)
    if flash:
        kind, text = flash
        if kind == "success":
            st.success(text)
        else:
            st.error(text)

    st.caption(
        "These accounts sign in when **LEGACY_AUTH_SOURCE=db**. Passwords are stored as Argon2 hashes only."
    )

    try:
        users = app_user_service.list_users()
    except AppUserError as exc:
        st.error(str(exc))
        return

    my_uid = st.session_state.get("user_id")

    with st.container(border=True):
        st.markdown("**Create user**")
        with st.form("admin_app_user_create", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                new_username = st.text_input("Username", placeholder="e.g. jane")
            with c2:
                new_role = st.selectbox("Role", ["admin", "validator"], index=0)
            np1 = st.text_input("Password", type="password")
            np2 = st.text_input("Confirm password", type="password")
            create_sub = st.form_submit_button("Create user")
        if create_sub:
            if np1 != np2:
                st.session_state._admin_app_user_flash = ("error", "Passwords do not match.")
                st.rerun()
            try:
                app_user_service.create_user(new_username, np1, new_role)
                st.session_state._admin_app_user_flash = ("success", f"Created user **{new_username.strip().lower()}**.")
                st.rerun()
            except WritesDisabledError as exc:
                st.warning(str(exc))
            except AppUserError as exc:
                st.session_state._admin_app_user_flash = ("error", str(exc))
                st.rerun()

    if users:
        df = pd.DataFrame(users)
        for col in ("created_at", "updated_at"):
            if col in df.columns:
                df[col] = df[col].astype(str)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No **app_user** rows yet. Create one above (or use the CLI seed script).")

    for row in users:
        uid = int(row["user_id"])
        uname = row["username"]
        label = f"**{uname}** — {row['role']}, active={row['is_active']}"
        with st.expander(label):
            st.caption(f"user_id={uid}")
            with st.form(f"admin_app_user_pwd_{uid}"):
                p1 = st.text_input("New password", type="password", key=f"au_p1_{uid}")
                p2 = st.text_input("Confirm new password", type="password", key=f"au_p2_{uid}")
                if st.form_submit_button("Update password"):
                    if p1 != p2:
                        st.session_state._admin_app_user_flash = ("error", "Passwords do not match.")
                        st.rerun()
                    try:
                        app_user_service.set_password(uid, p1)
                        st.session_state._admin_app_user_flash = ("success", f"Password updated for **{uname}**.")
                        st.rerun()
                    except WritesDisabledError as exc:
                        st.warning(str(exc))
                    except AppUserError as exc:
                        st.session_state._admin_app_user_flash = ("error", str(exc))
                        st.rerun()

            role_idx = 0 if row["role"] == "admin" else 1
            with st.form(f"admin_app_user_role_{uid}"):
                new_role = st.selectbox(
                    "Role",
                    ["admin", "validator"],
                    index=role_idx,
                    key=f"au_role_{uid}",
                )
                if st.form_submit_button("Save role"):
                    try:
                        app_user_service.change_role(uid, new_role)
                        st.session_state._admin_app_user_flash = ("success", f"Role set to **{new_role}** for **{uname}**.")
                        st.rerun()
                    except WritesDisabledError as exc:
                        st.warning(str(exc))
                    except AppUserError as exc:
                        st.session_state._admin_app_user_flash = ("error", str(exc))
                        st.rerun()

            active = bool(row["is_active"])
            if my_uid is not None and uid == int(my_uid) and active:
                st.caption("You cannot deactivate your own account here — use another admin if needed.")
            else:
                col_a, col_b = st.columns(2)
                with col_a:
                    if active:
                        if st.button("Deactivate", key=f"au_deact_{uid}"):
                            try:
                                app_user_service.set_active(uid, False)
                                st.session_state._admin_app_user_flash = ("success", f"Deactivated **{uname}**.")
                                st.rerun()
                            except WritesDisabledError as exc:
                                st.warning(str(exc))
                            except AppUserError as exc:
                                st.session_state._admin_app_user_flash = ("error", str(exc))
                                st.rerun()
                with col_b:
                    if not active:
                        if st.button("Activate", key=f"au_act_{uid}"):
                            try:
                                app_user_service.set_active(uid, True)
                                st.session_state._admin_app_user_flash = ("success", f"Activated **{uname}**.")
                                st.rerun()
                            except WritesDisabledError as exc:
                                st.warning(str(exc))
                            except AppUserError as exc:
                                st.session_state._admin_app_user_flash = ("error", str(exc))
                                st.rerun()


@st.cache_data(ttl=60)
def _property_name(property_id: int) -> str:
    props = property_service.get_all_properties()
    for p in props:
        if p["property_id"] == property_id:
            return p["name"]
    return f"Property {property_id}"

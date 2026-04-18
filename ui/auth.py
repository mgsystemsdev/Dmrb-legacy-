from __future__ import annotations

import streamlit as st

from config.settings import (
    APP_PASSWORD,
    APP_USERNAME,
    AUTH_DISABLED,
    LEGACY_AUTH_SOURCE,
    VALIDATOR_PASSWORD,
    VALIDATOR_USERNAME,
)
from services import auth_service


def _login_credentials_configured() -> bool:
    full = bool(APP_USERNAME and APP_PASSWORD)
    validator = bool(VALIDATOR_USERNAME and VALIDATOR_PASSWORD)
    return full or validator


def _require_auth_env() -> bool:
    if not _login_credentials_configured():
        st.session_state.authenticated = True
        st.session_state.access_mode = "full"
        st.session_state.pop("user_id", None)
        st.session_state.pop("username", None)
        return True

    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("login_form"):
            st.subheader("Login")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in")

        if submitted:
            if (
                VALIDATOR_USERNAME
                and VALIDATOR_PASSWORD
                and username == VALIDATOR_USERNAME
                and password == VALIDATOR_PASSWORD
            ):
                st.session_state.authenticated = True
                st.session_state.access_mode = "validator_only"
                st.session_state.pop("user_id", None)
                st.session_state.pop("username", None)
                st.rerun()
            elif username == APP_USERNAME and password == APP_PASSWORD:
                st.session_state.authenticated = True
                st.session_state.access_mode = "full"
                st.session_state.pop("user_id", None)
                st.session_state.pop("username", None)
                st.rerun()
            else:
                st.error("Invalid username or password.")

    return False


def _require_auth_db() -> bool:
    from db.repository import user_repository

    _, col, _ = st.columns([1, 2, 1])
    with col:
        if "_db_user_total" not in st.session_state:
            try:
                st.session_state._db_user_total = user_repository.count_all()
            except Exception:
                st.session_state._db_user_total = -1

        n = st.session_state._db_user_total
        if n == 0:
            st.warning(
                "No users in **app_user**. Either: sign in with **env** login (`LEGACY_AUTH_SOURCE=env`), "
                "open **Admin → App users**, enable **DB Writes**, and **Create user** — "
                "or use the CLI from **dmrb/dmrb-legacy**: "
                "`python3 scripts/create_app_user.py --username … --role admin`."
            )
        elif n < 0:
            st.error("Could not read **app_user**. Check DATABASE_URL and database availability.")

        with st.form("login_form"):
            st.subheader("Login")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in")

        if submitted:
            result = auth_service.authenticate(username, password)
            if result:
                st.session_state.authenticated = True
                st.session_state.access_mode = result["access_mode"]
                st.session_state.user_id = result["user_id"]
                st.session_state.username = result["username"]
                st.rerun()
            else:
                st.error("Invalid username or password.")

    return False


def require_auth() -> bool:
    if st.session_state.get("authenticated"):
        return True

    if AUTH_DISABLED:
        st.session_state.authenticated = True
        st.session_state.access_mode = "full"
        st.session_state.pop("user_id", None)
        st.session_state.pop("username", None)
        return True

    if LEGACY_AUTH_SOURCE == "db":
        return _require_auth_db()
    return _require_auth_env()

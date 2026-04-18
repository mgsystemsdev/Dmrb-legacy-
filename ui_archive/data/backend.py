from __future__ import annotations

import streamlit as st

from db.migration_runner import ensure_database_ready


@st.cache_resource
def _bootstrap():
    ensure_database_ready()


def bootstrap_backend() -> None:
    _bootstrap()

"""Application configuration resolver."""

from __future__ import annotations

import os
from typing import Any


def _load_streamlit_secrets() -> dict[str, Any]:
    try:
        import streamlit as st

        return dict(st.secrets)
    except Exception:
        return {}


def get_setting(key: str, default: Any = None) -> Any:
    value = os.getenv(key)
    if value is not None:
        return value
    return _load_streamlit_secrets().get(key, default)


def is_truthy_setting(key: str) -> bool:
    v = get_setting(key, "")
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "on")


DATABASE_URL = get_setting("DATABASE_URL", "")
SUPABASE_URL = get_setting("SUPABASE_URL", "")
SUPABASE_KEY = get_setting("SUPABASE_KEY", "")
APP_USERNAME = get_setting("APP_USERNAME", "")
APP_PASSWORD = get_setting("APP_PASSWORD", "")
VALIDATOR_USERNAME = get_setting("VALIDATOR_USERNAME", "")
VALIDATOR_PASSWORD = get_setting("VALIDATOR_PASSWORD", "")

# Streamlit login: "env" = APP_* / VALIDATOR_* (default). "db" = public.app_user + Argon2.
_LEGACY_AUTH_SRC = (get_setting("LEGACY_AUTH_SOURCE", "env") or "env").strip().lower()
LEGACY_AUTH_SOURCE = _LEGACY_AUTH_SRC if _LEGACY_AUTH_SRC in ("env", "db") else "env"
AUTH_DISABLED = is_truthy_setting("AUTH_DISABLED")

OPENAI_API_KEY = get_setting("OPENAI_API_KEY", "") or ""
OPENAI_CHAT_MODEL = get_setting("OPENAI_CHAT_MODEL", "gpt-4o-mini") or "gpt-4o-mini"


FEATURE_FLAGS = {
    "example": get_setting("FEATURE_FLAG_EXAMPLE", False),
}

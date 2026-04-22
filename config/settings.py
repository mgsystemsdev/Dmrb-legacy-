"""Application configuration resolver."""

from __future__ import annotations

import os
from pathlib import Path
import tomllib
from typing import Any


def _load_streamlit_secrets() -> dict[str, Any]:
    try:
        secrets_path = Path(".streamlit/secrets.toml")
        if not secrets_path.exists():
            return {}
        with secrets_path.open("rb") as fh:
            return tomllib.load(fh)
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

_DEFAULT_SECRET_KEY = "dev-secret-key-change-me-in-production"
SECRET_KEY = get_setting("SECRET_KEY", _DEFAULT_SECRET_KEY)

IS_PRODUCTION = bool(
    os.getenv("RAILWAY_ENVIRONMENT_NAME")
    or os.getenv("RAILWAY_ENVIRONMENT")
    or is_truthy_setting("PRODUCTION")
)
SESSION_COOKIE_SECURE = IS_PRODUCTION or is_truthy_setting("SESSION_COOKIE_SECURE")

if IS_PRODUCTION and SECRET_KEY == _DEFAULT_SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY must be set to a strong value in production. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    )

# API auth uses public.app_user only. Kept for Streamlit / legacy: "env" = APP_*, "db" = app_user.
_LEGACY_AUTH_SRC = (get_setting("LEGACY_AUTH_SOURCE", "db") or "db").strip().lower()
LEGACY_AUTH_SOURCE = _LEGACY_AUTH_SRC if _LEGACY_AUTH_SRC in ("env", "db") else "db"
AUTH_DISABLED = is_truthy_setting("AUTH_DISABLED")

OPENAI_API_KEY = get_setting("OPENAI_API_KEY", "") or ""
OPENAI_CHAT_MODEL = get_setting("OPENAI_CHAT_MODEL", "gpt-4o-mini") or "gpt-4o-mini"


FEATURE_FLAGS = {
    "example": get_setting("FEATURE_FLAG_EXAMPLE", False),
}

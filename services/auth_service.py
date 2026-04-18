from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from config.settings import (
    APP_PASSWORD,
    APP_USERNAME,
    AUTH_DISABLED,
    LEGACY_AUTH_SOURCE,
    VALIDATOR_PASSWORD,
    VALIDATOR_USERNAME,
)
from db.repository import user_repository

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(password_hash: str, plain: str) -> bool:
    try:
        _hasher.verify(password_hash, plain)
        return True
    except VerifyMismatchError:
        return False


def login_credentials_configured() -> bool:
    full = bool(APP_USERNAME and APP_PASSWORD)
    validator = bool(VALIDATOR_USERNAME and VALIDATOR_PASSWORD)
    return full or validator


def build_bypass_user() -> dict:
    return {
        "user_id": 0,
        "username": "dev",
        "role": "admin",
        "access_mode": "full",
    }


def should_auto_auth() -> bool:
    if AUTH_DISABLED:
        return True
    if LEGACY_AUTH_SOURCE == "env" and not login_credentials_configured():
        return True
    return False


def _authenticate_env(username: str, password: str) -> dict | None:
    if (
        VALIDATOR_USERNAME
        and VALIDATOR_PASSWORD
        and username == VALIDATOR_USERNAME
        and password == VALIDATOR_PASSWORD
    ):
        return {
            "user_id": 0,
            "username": VALIDATOR_USERNAME,
            "role": "validator",
            "access_mode": "validator_only",
        }

    if APP_USERNAME and APP_PASSWORD and username == APP_USERNAME and password == APP_PASSWORD:
        return {
            "user_id": 0,
            "username": APP_USERNAME,
            "role": "admin",
            "access_mode": "full",
        }

    return None


def _authenticate_db(username: str, password: str) -> dict | None:
    """Return session fields on success, or None if login fails."""
    row = user_repository.get_active_by_username(username)
    if row is None:
        return None
    if not verify_password(row["password_hash"], password):
        return None
    role = row["role"]
    access_mode = "validator_only" if role == "validator" else "full"
    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "role": role,
        "access_mode": access_mode,
    }


def authenticate(username: str, password: str) -> dict | None:
    """Return session fields on success, or None if login fails."""
    if AUTH_DISABLED:
        return build_bypass_user()

    if LEGACY_AUTH_SOURCE == "env":
        if not login_credentials_configured():
            return build_bypass_user()
        return _authenticate_env(username, password)

    return _authenticate_db(username, password)

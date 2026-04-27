from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from config.settings import AUTH_DISABLED, IS_PRODUCTION, is_truthy_setting
from db.connection import transaction
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


def build_bypass_user() -> dict:
    return {
        "user_id": 0,
        "username": "dev",
        "role": "admin",
        "access_mode": "full",
    }


def should_auto_auth() -> bool:
    """Only AUTH_DISABLED enables unauthenticated API access."""
    return bool(AUTH_DISABLED)


def get_bootstrap_status_payload() -> dict:
    """Single source of truth for GET /api/auth/bootstrap-status (and needs_bootstrap())."""
    allow = is_truthy_setting("ALLOW_API_BOOTSTRAP")
    try:
        user_count = user_repository.count_all()
    except Exception:
        return {
            "needs_bootstrap": False,
            "user_count": -1,
            "auth_disabled": bool(AUTH_DISABLED),
            "is_production": bool(IS_PRODUCTION),
            "allow_api_bootstrap": allow,
            "reason": "user_count_error",
        }
    if AUTH_DISABLED:
        return {
            "needs_bootstrap": False,
            "user_count": user_count,
            "auth_disabled": True,
            "is_production": bool(IS_PRODUCTION),
            "allow_api_bootstrap": allow,
            "reason": "auth_disabled",
        }
    if user_count > 0:
        return {
            "needs_bootstrap": False,
            "user_count": user_count,
            "auth_disabled": False,
            "is_production": bool(IS_PRODUCTION),
            "allow_api_bootstrap": allow,
            "reason": "users_exist",
        }
    if IS_PRODUCTION and not allow:
        return {
            "needs_bootstrap": False,
            "user_count": 0,
            "auth_disabled": False,
            "is_production": True,
            "allow_api_bootstrap": False,
            "reason": "production_requires_ALLOW_API_BOOTSTRAP",
        }
    return {
        "needs_bootstrap": True,
        "user_count": 0,
        "auth_disabled": False,
        "is_production": bool(IS_PRODUCTION),
        "allow_api_bootstrap": allow,
        "reason": None,
    }


def needs_bootstrap() -> bool:
    return bool(get_bootstrap_status_payload()["needs_bootstrap"])


def bootstrap_create_first_admin(username: str, password: str) -> dict:
    """Create the first admin in ``app_user``. Transaction-safe; raises ValueError if not allowed."""
    u = (username or "").strip()
    if not u:
        raise ValueError("username_required")
    with transaction():
        user_repository.acquire_bootstrap_advisory_lock()
        if user_repository.count_all() > 0:
            raise ValueError("already_bootstrapped")
        ph = hash_password(password)
        row = user_repository.insert(u, ph, "admin")
    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "role": row["role"],
        "access_mode": "full",
    }


def _authenticate_db(username: str, password: str) -> dict | None:
    import logging

    logger = logging.getLogger(__name__)
    row = user_repository.get_active_by_username(username)
    if row is None:
        logger.warning("Auth failed: user '%s' not found", username)
        return None
    if not verify_password(row["password_hash"], password):
        logger.warning("Auth failed: password mismatch for user '%s'", username)
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
    """DB-only: authenticate against ``app_user`` (Argon2)."""
    if AUTH_DISABLED:
        return build_bypass_user()
    return _authenticate_db(username, password)


def _delete_all_app_users() -> int:
    return user_repository.delete_all()


def reset_all_users() -> int:
    """Delete all rows in ``app_user``. Returns the number of rows removed."""
    with transaction():
        return _delete_all_app_users()


def dev_reset_to_single_admin(username: str, password: str) -> dict:
    """Remove every ``app_user`` row and create one active admin. Non-production / dev use only.

    Password is hashed with Argon2 before persistence. Atomic single transaction.
    """
    u = (username or "").strip()
    if not u:
        raise ValueError("username_required")
    if not (password or "").strip():
        raise ValueError("password_required")
    if len(password) < 8:
        raise ValueError("password_too_short")
    with transaction():
        _delete_all_app_users()
        ph = hash_password(password)
        row = user_repository.insert(u, ph, "admin")
    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "role": row["role"],
        "is_active": row["is_active"],
        "access_mode": "full",
    }

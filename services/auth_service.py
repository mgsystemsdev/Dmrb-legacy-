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


def needs_bootstrap() -> bool:
    """True when there are no app_user rows and first-run admin setup is allowed in this environment."""
    if AUTH_DISABLED:
        return False
    if user_repository.count_all() > 0:
        return False
    if IS_PRODUCTION and not is_truthy_setting("ALLOW_API_BOOTSTRAP"):
        return False
    return True


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
    """DB-only: authenticate against ``app_user`` (Argon2)."""
    if AUTH_DISABLED:
        return build_bypass_user()
    return _authenticate_db(username, password)

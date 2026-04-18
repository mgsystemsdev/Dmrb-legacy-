from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

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


def authenticate(username: str, password: str) -> dict | None:
    """Return session fields on success, or None if login fails (unknown user or bad password)."""
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

"""Signed session cookie for API login (used by /api/login and /api/auth/bootstrap)."""

from __future__ import annotations

import time

from fastapi import Response
from itsdangerous import URLSafeTimedSerializer

from config.settings import SECRET_KEY, SESSION_COOKIE_SECURE

AUTH_COOKIE_NAME = "session"
_serializer = URLSafeTimedSerializer(SECRET_KEY)


def set_session_cookie(response: Response, result: dict) -> None:
    session_data = {
        "user_id": result["user_id"],
        "username": result["username"],
        "role": result.get("role", "admin"),
        "access_mode": result.get("access_mode", "full"),
        "exp": int(time.time()) + 3600 * 24,
    }
    token = _serializer.dumps(session_data, salt="auth-session")
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=SESSION_COOKIE_SECURE,
        max_age=3600 * 24,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=AUTH_COOKIE_NAME)

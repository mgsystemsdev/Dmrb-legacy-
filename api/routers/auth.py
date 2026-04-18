from __future__ import annotations
import time
from fastapi import APIRouter, Response, HTTPException
from itsdangerous import URLSafeTimedSerializer
from api.schemas.auth import LoginRequest
from services import auth_service
from config.settings import SECRET_KEY

router = APIRouter()
serializer = URLSafeTimedSerializer(SECRET_KEY)
AUTH_COOKIE_NAME = "session"

@router.post("/login")
async def login(request: LoginRequest, response: Response):
    result = auth_service.authenticate(request.username, request.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # result contains: user_id, username, role, access_mode
    session_data = {
        "user_id": result["user_id"],
        "username": result["username"],
        "role": result["role"],
        "exp": int(time.time()) + 3600 * 24 # 24 hours
    }

    token = serializer.dumps(session_data, salt="auth-session")

    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False, # Set to True in production with HTTPS
        max_age=3600 * 24
    )

    return {"status": "ok"}

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(AUTH_COOKIE_NAME)
    return {"status": "ok"}

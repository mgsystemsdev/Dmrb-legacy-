from __future__ import annotations
from fastapi import APIRouter, Depends
from api.deps import get_current_user

router = APIRouter()


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "user_id": user.get("user_id"),
        "username": user.get("username"),
        "role": user.get("role"),
        "access_mode": user.get("access_mode", "full"),
    }

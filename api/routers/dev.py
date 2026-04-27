from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from api.schemas.dev import DevResetAdminRequest
from api.session_cookie import set_session_cookie
from config.settings import allow_dev_reset_admin_endpoint
from services import auth_service

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/reset-admin")
async def reset_admin(request: DevResetAdminRequest, response: Response):
    """Wipe ``app_user`` and create a single admin (non-production only)."""
    if not allow_dev_reset_admin_endpoint():
        raise HTTPException(
            status_code=403, detail="This endpoint is only available in development."
        )

    uname = request.username.strip()
    if not uname:
        raise HTTPException(status_code=400, detail="Username is required.")

    try:
        result = auth_service.dev_reset_to_single_admin(uname, request.password)
    except ValueError as e:
        code = str(e)
        if code == "username_required":
            raise HTTPException(status_code=400, detail="Username is required.") from e
        if code == "password_required":
            raise HTTPException(status_code=400, detail="Password is required.") from e
        if code == "password_too_short":
            raise HTTPException(
                status_code=400, detail="Password must be at least 8 characters."
            ) from e
        raise HTTPException(status_code=400, detail="Could not reset admin user.") from e

    set_session_cookie(response, result)
    return {
        "status": "ok",
        "username": result["username"],
        "user_id": result["user_id"],
        "role": result["role"],
    }

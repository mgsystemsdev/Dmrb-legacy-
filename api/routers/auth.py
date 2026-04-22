from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from api.deps import get_current_user
from api.schemas.auth import BootstrapRequest
from api.session_cookie import set_session_cookie
from services import auth_service

router = APIRouter()


@router.get("/auth/bootstrap-status")
async def bootstrap_status():
    data = auth_service.get_bootstrap_status_payload()
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "no-store"},
    )


@router.post("/auth/bootstrap")
async def bootstrap_admin(request: BootstrapRequest, response: Response):
    if not auth_service.needs_bootstrap():
        raise HTTPException(status_code=400, detail="Setup is not available or was already completed.")

    uname = request.username.strip()
    if not uname:
        raise HTTPException(status_code=400, detail="Username is required.")

    if request.password != request.password_confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    pwd = request.password
    if len(pwd) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    try:
        result = auth_service.bootstrap_create_first_admin(uname, pwd)
    except ValueError as e:
        code = str(e)
        if code == "already_bootstrapped":
            raise HTTPException(status_code=400, detail="Setup was already completed.") from e
        if code == "username_required":
            raise HTTPException(status_code=400, detail="Username is required.") from e
        raise HTTPException(status_code=400, detail="Could not create admin user.") from e

    set_session_cookie(response, result)
    return {"status": "ok", "username": result["username"]}


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "user_id": user.get("user_id"),
        "username": user.get("username"),
        "role": user.get("role"),
        "access_mode": user.get("access_mode", "full"),
    }

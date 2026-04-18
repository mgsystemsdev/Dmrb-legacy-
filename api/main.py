from __future__ import annotations
from pathlib import Path
import time
from fastapi import FastAPI, Response, HTTPException
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer
from api.middleware.request_id import RequestIDMiddleware
from api.middleware.auth import AuthMiddleware
from api.routers import auth, board, health, imports, notes, pages, properties, tasks, turnovers, units
from api.schemas.auth import LoginRequest
from services import auth_service
from config.settings import SECRET_KEY

app = FastAPI(title="DMRB Legacy API")

app.add_middleware(RequestIDMiddleware)
app.add_middleware(AuthMiddleware)

app.mount("/static", StaticFiles(directory="static"), name="static")

# JSON API routes
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(board.router, prefix="/api", tags=["board"])
app.include_router(imports.router, prefix="/api", tags=["imports"])
app.include_router(properties.router, prefix="/api", tags=["properties"])
app.include_router(turnovers.router, prefix="/api", tags=["turnovers"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(notes.router, prefix="/api", tags=["notes"])
app.include_router(units.router, prefix="/api", tags=["units"])

frontend_dist = Path("frontend/dist")

if frontend_dist.exists():
    # Once the SPA is built, it owns /login, /board, and the rest of the app shell.
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="spa")
else:
    # Preserve the legacy server-rendered pages until the SPA build exists.
    app.include_router(pages.router, tags=["pages"])

serializer = URLSafeTimedSerializer(SECRET_KEY)
AUTH_COOKIE_NAME = "session"


@app.post("/api/login", tags=["auth"])
async def api_login(request: LoginRequest, response: Response):
    """JSON login endpoint for API clients."""
    result = auth_service.authenticate(request.username, request.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    session_data = {
        "user_id": result["user_id"],
        "username": result["username"],
        "role": result["role"],
        "exp": int(time.time()) + 3600 * 24,
    }
    token = serializer.dumps(session_data, salt="auth-session")
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=3600 * 24,
    )
    return {"status": "ok"}


@app.post("/api/logout", tags=["auth"])
async def api_logout(response: Response):
    """JSON logout endpoint for API clients."""
    response.delete_cookie(AUTH_COOKIE_NAME)
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

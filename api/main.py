from __future__ import annotations
import logging
from pathlib import Path
import time
from fastapi import FastAPI, Response, HTTPException
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer
from api.middleware.request_id import RequestIDMiddleware
from api.middleware.auth import AuthMiddleware
from api.routers import auth, board, health, imports, notes, operations, properties, tasks, turnovers, unit_master, units
from api.schemas.auth import LoginRequest
from services import auth_service
from config.settings import SECRET_KEY, SESSION_COOKIE_SECURE

logger = logging.getLogger(__name__)

app = FastAPI(title="DMRB Legacy API")


@app.on_event("startup")
async def _apply_migrations() -> None:
    """Run idempotent schema + incremental migrations before serving traffic.

    Failures are logged loudly but do NOT crash the app — this ensures the
    public /healthz endpoint stays reachable so Railway's deploy can finish
    and surface the real error in logs (usually a missing/invalid
    DATABASE_URL). Real request handlers will still fail fast if the DB is
    unreachable.
    """
    from db.migration_runner import ensure_database_ready

    try:
        ensure_database_ready()
        logger.info("Database migrations applied successfully")
    except Exception as exc:
        logger.error(
            "Database migration on startup failed (app will start anyway "
            "so /healthz responds; set DATABASE_URL and redeploy): %s",
            exc,
        )


@app.get("/healthz", tags=["health"])
async def healthz():
    """Public, unauthenticated liveness probe for Railway health checks."""
    return {"status": "ok"}


app.add_middleware(RequestIDMiddleware)
app.add_middleware(AuthMiddleware)

# JSON API routes
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(board.router, prefix="/api", tags=["board"])
app.include_router(imports.router, prefix="/api", tags=["imports"])
app.include_router(operations.router, prefix="/api", tags=["operations"])
app.include_router(properties.router, prefix="/api", tags=["properties"])
app.include_router(turnovers.router, prefix="/api", tags=["turnovers"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(notes.router, prefix="/api", tags=["notes"])
app.include_router(units.router, prefix="/api", tags=["units"])
app.include_router(unit_master.router, prefix="/api")

frontend_dist = Path("frontend/dist")
if not frontend_dist.exists():
    raise RuntimeError("Missing React build at frontend/dist. Run the frontend build before starting FastAPI.")

app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="spa")

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
        secure=SESSION_COOKIE_SECURE,
        max_age=3600 * 24,
    )
    return {"status": "ok"}


@app.post("/api/logout", tags=["auth"])
async def api_logout(response: Response):
    """JSON logout endpoint for API clients."""
    response.delete_cookie(AUTH_COOKIE_NAME)
    return {"status": "ok"}


if __name__ == "__main__":
    import os
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )

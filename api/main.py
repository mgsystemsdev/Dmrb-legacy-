from __future__ import annotations
import logging
from pathlib import Path
from fastapi import FastAPI, Response, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from api.middleware.request_id import RequestIDMiddleware
from api.middleware.auth import AuthMiddleware
from api.routers import (
    auth,
    board,
    dev,
    health,
    imports,
    notes,
    operations,
    phase_scope,
    properties,
    tasks,
    turnovers,
    unit_master,
    units,
)
from api.schemas.auth import LoginRequest
from api.session_cookie import clear_session_cookie, set_session_cookie
from config import settings
from services import auth_service

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

if settings.allow_dev_reset_admin_endpoint():
    app.include_router(dev.router, prefix="/api")

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(board.router, prefix="/api", tags=["board"])
app.include_router(imports.router, prefix="/api", tags=["imports"])
app.include_router(operations.router, prefix="/api", tags=["operations"])
app.include_router(properties.router, prefix="/api", tags=["properties"])
app.include_router(turnovers.router, prefix="/api", tags=["turnovers"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(notes.router, prefix="/api", tags=["notes"])
app.include_router(units.router, prefix="/api", tags=["units"])
app.include_router(phase_scope.router, prefix="/api", tags=["phase-scope"])
app.include_router(unit_master.router, prefix="/api")

frontend_dist = Path("frontend/dist")
if not frontend_dist.exists():
    raise RuntimeError("Missing React build at frontend/dist. Run the frontend build before starting FastAPI.")

FRONTEND_INDEX = frontend_dist / "index.html"
ASSETS_DIR = frontend_dist / "assets"
if ASSETS_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="static-assets")


def _is_safe_file_under_dist(candidate: Path) -> bool:
    dist = frontend_dist.resolve()
    try:
        candidate.resolve().relative_to(dist)
    except ValueError:
        return False
    return candidate.is_file()


@app.get("/")
def serve_spa_index() -> FileResponse:
    return FileResponse(FRONTEND_INDEX, media_type="text/html")


@app.get("/{full_path:path}")
def serve_spa_routes(full_path: str) -> FileResponse:
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    candidate = frontend_dist / full_path
    if _is_safe_file_under_dist(candidate):
        return FileResponse(candidate)
    return FileResponse(FRONTEND_INDEX, media_type="text/html")


@app.post("/api/login", tags=["auth"])
async def api_login(request: LoginRequest, response: Response):
    """JSON login endpoint for API clients."""
    result = auth_service.authenticate(request.username, request.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    set_session_cookie(response, result)
    return {"status": "ok"}


@app.post("/api/logout", tags=["auth"])
async def api_logout(response: Response):
    """JSON logout endpoint for API clients."""
    clear_session_cookie(response)
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

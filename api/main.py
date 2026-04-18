from __future__ import annotations
import logging
import os
from pathlib import Path
import time
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer
from api.middleware.request_id import RequestIDMiddleware
from api.middleware.auth import AuthMiddleware
from api.routers import auth, board, health, imports, notes, operations, properties, tasks, turnovers, units
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

    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        # Mask credentials in the log so the URL is identifiable but safe
        try:
            from urllib.parse import urlparse
            parsed = urlparse(db_url)
            safe_url = f"{parsed.scheme}://***@{parsed.hostname}:{parsed.port}{parsed.path}"
        except Exception:
            safe_url = "<unparseable>"
        logger.info("DATABASE_URL is set — connecting to: %s", safe_url)
    else:
        logger.error(
            "DATABASE_URL is not set — database operations will fail. "
            "Add the DATABASE_URL environment variable and redeploy."
        )

    t0 = time.monotonic()
    try:
        ensure_database_ready()
        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.info("Database migrations applied successfully (%.0f ms)", elapsed_ms)
    except Exception as exc:
        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.error(
            "Database migration on startup failed after %.0f ms "
            "(app will start anyway so /healthz responds; "
            "set DATABASE_URL and redeploy): [%s] %s",
            elapsed_ms,
            type(exc).__name__,
            exc,
        )


@app.on_event("startup")
async def _check_frontend_dist() -> None:
    """Verify the React build directory exists and is non-empty at startup."""
    frontend_dist = Path("frontend/dist")
    if not frontend_dist.exists():
        logger.error(
            "Frontend dist directory does not exist at '%s' (cwd: %s). "
            "The SPA will not be served. Run the frontend build step.",
            frontend_dist.resolve(),
            Path.cwd(),
        )
        return

    files = list(frontend_dist.rglob("*"))
    html_files = [f for f in files if f.suffix == ".html"]
    js_files = [f for f in files if f.suffix == ".js"]
    logger.info(
        "Frontend dist directory found at '%s': %d total files, "
        "%d HTML, %d JS",
        frontend_dist.resolve(),
        len(files),
        len(html_files),
        len(js_files),
    )
    index_html = frontend_dist / "index.html"
    if not index_html.exists():
        logger.error(
            "index.html is missing from '%s' — the SPA will not load correctly.",
            frontend_dist.resolve(),
        )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log details of any unhandled exception so silent failures are visible."""
    request_id = getattr(request.state, "request_id", "-")
    logger.error(
        "Unhandled exception during %s %s (request_id=%s): [%s] %s",
        request.method,
        request.url.path,
        request_id,
        type(exc).__name__,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
    )


@app.get("/healthz", tags=["health"])
async def healthz():
    """Public, unauthenticated liveness probe for Railway health checks."""
    return {"status": "ok"}


@app.get("/", tags=["diagnostics"], include_in_schema=False)
async def root_probe():
    """Explicit root handler to confirm request routing works end-to-end.

    This route is registered before the StaticFiles SPA mount so it takes
    priority. It returns a minimal JSON response — if this times out the
    issue is in the ASGI stack or reverse proxy, not the frontend build.
    """
    frontend_dist = Path("frontend/dist")
    return {
        "status": "ok",
        "frontend_dist_exists": frontend_dist.exists(),
        "index_html_exists": (frontend_dist / "index.html").exists(),
    }


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

frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="spa")
else:
    logger.warning(
        "Skipping StaticFiles mount — frontend/dist not found. "
        "API routes will still work but the SPA will not be served."
    )

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

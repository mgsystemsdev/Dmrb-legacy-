from __future__ import annotations
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from config.settings import SECRET_KEY
from api.session_cookie import AUTH_COOKIE_NAME
from services import auth_service

_API_PUBLIC_PREFIXES = (
    "/api/login",
    "/api/logout",
    "/api/auth/bootstrap-status",
    "/api/auth/bootstrap",
    "/api/dev/reset-admin",
)


def _is_public_api_path(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in _API_PUBLIC_PREFIXES)

_PUBLIC_PATHS = frozenset({
    "/",
    "/login",
    "/logout",
    "/docs",
    "/openapi.json",
    "/api/docs",
    "/api/openapi.json",
    "/favicon.ico",
    "/vite.svg",
})


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.serializer = URLSafeTimedSerializer(SECRET_KEY)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if (
            path in _PUBLIC_PATHS
            or path.startswith("/static/")
            or path.startswith("/assets/")
            or not path.startswith("/api/")
        ):
            return await call_next(request)

        if path.startswith("/api/") and _is_public_api_path(path):
            return await call_next(request)

        if auth_service.should_auto_auth():
            request.state.user = auth_service.build_bypass_user()
            return await call_next(request)

        cookie = request.cookies.get(AUTH_COOKIE_NAME)
        if not cookie:
            return self._unauthenticated(request, path)

        try:
            data = self.serializer.loads(cookie, salt="auth-session")
            if data.get("exp") and time.time() > data["exp"]:
                return self._unauthenticated(request, path)
            request.state.user = data
        except (BadSignature, SignatureExpired):
            return self._unauthenticated(request, path)

        return await call_next(request)

    @staticmethod
    def _unauthenticated(request: Request, path: str) -> Response:
        if _is_htmx(request):
            return Response(status_code=401, headers={"HX-Redirect": "/login"})
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

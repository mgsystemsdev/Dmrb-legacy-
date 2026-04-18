from __future__ import annotations
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from config.settings import SECRET_KEY

AUTH_COOKIE_NAME = "session"

_PUBLIC_PATHS = frozenset({
    "/login",
    "/logout",
    "/docs",
    "/openapi.json",
    "/api/docs",
    "/api/openapi.json",
})


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _is_html_request(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.serializer = URLSafeTimedSerializer(SECRET_KEY)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in _PUBLIC_PATHS or path.startswith("/static/"):
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
        if _is_html_request(request):
            safe_next = path if path.startswith("/") else "/"
            return RedirectResponse(url=f"/login?next={safe_next}", status_code=302)
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

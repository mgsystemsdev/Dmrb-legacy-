from __future__ import annotations
import json
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from config.settings import SECRET_KEY

AUTH_COOKIE_NAME = "session"

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.serializer = URLSafeTimedSerializer(SECRET_KEY)

    async def dispatch(self, request: Request, call_next):
        # Public paths
        if request.url.path in ["/login", "/logout", "/docs", "/openapi.json", "/api/docs", "/api/openapi.json"]:
            return await call_next(request)

        cookie = request.cookies.get(AUTH_COOKIE_NAME)
        if not cookie:
            return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

        try:
            # We don't necessarily need max_age here if we check exp in the payload,
            # but URLSafeTimedSerializer can also handle it.
            # The prompt says payload has "exp".
            data = self.serializer.loads(cookie, salt="auth-session")
            
            import time
            if data.get("exp") and time.time() > data["exp"]:
                return JSONResponse(status_code=401, content={"detail": "Session expired"})
                
            request.state.user = data
        except (BadSignature, SignatureExpired):
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired session"})

        return await call_next(request)

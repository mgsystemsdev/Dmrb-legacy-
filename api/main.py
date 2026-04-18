from __future__ import annotations
import time
from fastapi import FastAPI, Response, HTTPException
from itsdangerous import URLSafeTimedSerializer
from api.middleware.request_id import RequestIDMiddleware
from api.middleware.auth import AuthMiddleware
from api.routers import health, board, imports
from api.schemas.auth import LoginRequest
from services import auth_service
from config.settings import SECRET_KEY

app = FastAPI(title="DMRB Legacy API")

# Add middleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(AuthMiddleware)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(board.router, prefix="/api", tags=["board"])
app.include_router(imports.router, prefix="/api", tags=["imports"])

serializer = URLSafeTimedSerializer(SECRET_KEY)
AUTH_COOKIE_NAME = "session"

@app.post("/login")
async def login(request: LoginRequest, response: Response):
    result = auth_service.authenticate(request.username, request.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    session_data = {
        "user_id": result["user_id"],
        "username": result["username"],
        "role": result["role"],
        "exp": int(time.time()) + 3600 * 24 # 24 hours
    }

    token = serializer.dumps(session_data, salt="auth-session")

    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=3600 * 24
    )

    return {"status": "ok"}

@app.post("/logout")
async def logout(response: Response):
    response.delete_cookie(AUTH_COOKIE_NAME)
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

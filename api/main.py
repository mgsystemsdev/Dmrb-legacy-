from __future__ import annotations
from fastapi import FastAPI
from api.middleware.request_id import RequestIDMiddleware
from api.middleware.auth import AuthMiddleware
from api.routers import health, auth

app = FastAPI(title="DMRB Legacy API")

# Add middleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(AuthMiddleware)

# Include routers
app.include_router(auth.router, tags=["auth"])
app.include_router(health.router, tags=["health"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

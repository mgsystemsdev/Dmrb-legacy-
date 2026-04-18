from __future__ import annotations
from fastapi import APIRouter, Depends
from api.schemas.health import HealthResponse
from api.deps import get_current_user
from db.connection import get_pool_stats

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check(user: dict = Depends(get_current_user)):
    return {
        "status": "healthy",
        "db_pool": get_pool_stats()
    }

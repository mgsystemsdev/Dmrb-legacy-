from __future__ import annotations
from pydantic import BaseModel
from typing import Dict, Any

class HealthResponse(BaseModel):
    status: str
    db_pool: Dict[str, Any]

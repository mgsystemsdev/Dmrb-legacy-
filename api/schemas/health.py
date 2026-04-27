from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    db_pool: Dict[str, Any]
    queue_depth: int

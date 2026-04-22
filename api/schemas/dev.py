from __future__ import annotations

from pydantic import BaseModel, Field


class DevResetAdminRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    batch_id: Optional[int]
    status: str
    checksum: str
    diagnostics: List[str]


class BatchStatusResponse(BaseModel):
    batch_id: int
    property_id: int
    report_type: str
    status: str
    record_count: int
    created_at: datetime
    updated_at: datetime
    summary: Optional[Dict[str, int]] = None

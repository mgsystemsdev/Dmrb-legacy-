"""Audit service — provides audit log access for UI consumption."""

from __future__ import annotations

from db.repository import audit_repository


def get_turnover_history(turnover_id: int, limit: int = 100) -> list[dict]:
    return audit_repository.get_by_entity("turnover", turnover_id, limit=limit)

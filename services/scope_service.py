"""Scope service — persistent phase scope per (user, property).

Resolves and updates the active phase scope (query-time visibility filter).
When no per-user row exists, :func:`get_phase_scope` returns all phases for the property.
"""

from __future__ import annotations

from db.repository import phase_scope_repository, property_repository


def get_phase_scope(user_id: int, property_id: int) -> list[int]:
    """Return the list of phase_ids in scope for this user and property.

    If the user has no stored row, returns all phase_ids for the property.
    If a row exists, returns stored phase_ids that belong to the property (invalid
    phases are filtered out).
    """
    scope_row = phase_scope_repository.get_by_user_and_property(user_id, property_id)
    all_phases = property_repository.get_phases(property_id)
    property_phase_ids = {p["phase_id"] for p in all_phases}

    if scope_row is None:
        return [p["phase_id"] for p in all_phases]

    stored_ids = phase_scope_repository.get_phase_ids(scope_row["id"])
    return [pid for pid in stored_ids if pid in property_phase_ids]


def update_phase_scope(user_id: int, property_id: int, phase_ids: list[int]) -> None:
    """Replace the per-user active scope for the property.

    - Validates that every phase_id belongs to the property.
    - Replaces existing phase_scope_phase rows and updates updated_at.
    """
    all_phases = property_repository.get_phases(property_id)
    property_phase_ids = {p["phase_id"] for p in all_phases}
    for pid in phase_ids:
        if pid not in property_phase_ids:
            raise ValueError(f"Phase {pid} does not belong to property {property_id}")

    scope_row = phase_scope_repository.upsert_for_user(user_id, property_id)
    phase_scope_repository.set_phases(scope_row["id"], phase_ids)

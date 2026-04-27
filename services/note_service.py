"""Note service — coordinates note creation and resolution for turnovers."""

from __future__ import annotations

from db.repository import audit_repository, note_repository
from services.write_guard import check_writes_enabled


class NoteError(Exception):
    pass


def get_notes(turnover_id: int, include_resolved: bool = False) -> list[dict]:
    return note_repository.get_by_turnover(turnover_id, include_resolved=include_resolved)


def add_note(
    property_id: int,
    turnover_id: int,
    severity: str,
    text: str,
    actor: str = "system",
) -> dict:
    check_writes_enabled()
    if not text.strip():
        raise NoteError("Note text cannot be empty.")

    note = note_repository.insert(property_id, turnover_id, severity, text)

    audit_repository.insert(
        property_id=property_id,
        entity_type="note",
        entity_id=note["note_id"],
        field_name="created",
        old_value=None,
        new_value=text[:200],
        actor=actor,
        source="note_service",
    )
    return note


def resolve_note(note_id: int, actor: str = "system") -> dict:
    check_writes_enabled()
    note = note_repository.get_by_id(note_id)
    if note is None:
        raise NoteError(f"Note {note_id} not found.")

    resolved = note_repository.resolve(note_id)
    if resolved is None:
        raise NoteError(f"Note {note_id} is already resolved.")

    audit_repository.insert(
        property_id=resolved["property_id"],
        entity_type="note",
        entity_id=note_id,
        field_name="resolved",
        old_value=None,
        new_value="resolved",
        actor=actor,
        source="note_service",
    )
    return resolved

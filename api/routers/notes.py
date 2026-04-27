from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_current_user
from services import note_service
from services.note_service import NoteError

router = APIRouter()


class AddNoteRequest(BaseModel):
    severity: str
    text: str


@router.get("/turnovers/{turnover_id}/notes")
async def get_notes(
    turnover_id: int,
    include_resolved: bool = False,
    user: dict = Depends(get_current_user),
):
    return note_service.get_notes(turnover_id, include_resolved=include_resolved)


@router.post("/turnovers/{turnover_id}/notes")
async def add_note(
    turnover_id: int,
    body: AddNoteRequest,
    property_id: int,
    user: dict = Depends(get_current_user),
):
    try:
        return note_service.add_note(
            property_id,
            turnover_id,
            body.severity,
            body.text,
            actor=user.get("username", "api"),
        )
    except NoteError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/notes/{note_id}/resolve")
async def resolve_note(note_id: int, user: dict = Depends(get_current_user)):
    try:
        return note_service.resolve_note(note_id, actor=user.get("username", "api"))
    except NoteError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

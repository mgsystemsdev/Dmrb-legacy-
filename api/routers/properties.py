from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_current_user
from services import property_service

router = APIRouter()


@router.get("/properties")
async def list_properties(user: dict = Depends(get_current_user)):
    return property_service.get_all_properties()


@router.get("/properties/{property_id}/phases")
async def list_phases(property_id: int, user: dict = Depends(get_current_user)):
    return property_service.get_phases(property_id)


@router.get("/phases/{phase_id}/buildings")
async def list_buildings(phase_id: int, user: dict = Depends(get_current_user)):
    return property_service.get_buildings(phase_id)


@router.get("/buildings/{building_id}/units")
async def list_units_by_building(
    building_id: int,
    property_id: int,
    user: dict = Depends(get_current_user),
):
    return property_service.get_units_by_building(property_id, building_id)

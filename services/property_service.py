"""Property service — wraps property repository for UI consumption."""

from __future__ import annotations

from db.repository import property_repository, unit_repository
from services.write_guard import check_writes_enabled


def get_all_properties() -> list[dict]:
    return property_repository.get_all()


def get_property_by_id(property_id: int) -> dict | None:
    """Return the property row or None if missing."""
    return property_repository.get_by_id(property_id)


def get_phases(property_id: int) -> list[dict]:
    return property_repository.get_phases(property_id)


def get_buildings(phase_id: int) -> list[dict]:
    return property_repository.get_buildings(phase_id)


def get_phase_by_id(phase_id: int) -> dict | None:
    return property_repository.get_phase_by_id(phase_id)


def get_building_by_id(building_id: int) -> dict | None:
    return property_repository.get_building_by_id(building_id)


def get_units_by_building(
    property_id: int, building_id: int, *, active_only: bool = True,
) -> list[dict]:
    """Return units filtered to a specific building."""
    all_units = unit_repository.get_by_property(property_id, active_only=active_only)
    return [u for u in all_units if u.get("building_id") == building_id]


def get_units_by_phase(
    property_id: int, phase_id: int, *, active_only: bool = True,
) -> list[dict]:
    """Return units filtered to a specific phase."""
    all_units = unit_repository.get_by_property(property_id, active_only=active_only)
    return [u for u in all_units if u.get("phase_id") == phase_id]


def create_property(name: str) -> dict:
    check_writes_enabled()
    return property_repository.insert(name)


def create_phase(property_id: int, phase_code: str, name: str | None = None) -> dict:
    check_writes_enabled()
    phase = property_repository.insert_phase(property_id, phase_code, name)
    from services import task_service

    task_service.ensure_default_templates_for_phase(
        property_id, int(phase["phase_id"]),
    )
    return phase


def create_building(property_id: int, phase_id: int, building_code: str, name: str | None = None) -> dict:
    check_writes_enabled()
    return property_repository.insert_building(property_id, phase_id, building_code, name)


def create_unit(
    property_id: int,
    unit_code_raw: str,
    unit_code_norm: str,
    unit_identity_key: str,
    *,
    phase_id: int | None = None,
    building_id: int | None = None,
    floor_plan: str | None = None,
    gross_sq_ft: int | None = None,
    has_carpet: bool = False,
    has_wd_expected: bool = False,
) -> dict:
    check_writes_enabled()
    return unit_repository.insert(
        property_id, unit_code_raw, unit_code_norm, unit_identity_key,
        phase_id=phase_id, building_id=building_id,
        floor_plan=floor_plan, gross_sq_ft=gross_sq_ft,
        has_carpet=has_carpet, has_wd_expected=has_wd_expected,
    )


def get_phase_by_code(property_id: int, phase_code: str) -> dict | None:
    phases = property_repository.get_phases(property_id)
    for p in phases:
        if p["phase_code"] == phase_code:
            return p
    return None


def get_building_by_code(phase_id: int, building_code: str) -> dict | None:
    buildings = property_repository.get_buildings(phase_id)
    for b in buildings:
        if b["building_code"] == building_code:
            return b
    return None

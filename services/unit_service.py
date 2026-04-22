"""Unit service — unit listing and lookup.

Provides get_unit_detail read model for unit-detail screen (turnover + unit +
tasks + readiness + SLA + days_to_be_ready); interpretations computed here.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from db.repository import property_repository, unit_repository
from domain import turnover_lifecycle
from services import property_service, risk_service, scope_service, task_service, turnover_service
from services.write_guard import check_writes_enabled

if TYPE_CHECKING:
    import pandas as pd


class UnitMasterImportError(Exception):
    """Raised when a unit master CSV import cannot complete; no rows are committed."""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        msg = "; ".join(self.errors) if self.errors else "Unit master import failed"
        super().__init__(msg)


def get_unit_by_id(unit_id: int) -> dict | None:
    """Return unit by id. Read-only."""
    return unit_repository.get_by_id(unit_id)


def get_unit_by_code_norm(property_id: int, unit_code_norm: str) -> dict | None:
    """Return unit by normalized code within the property. Read-only."""
    return unit_repository.get_by_code_norm(property_id, unit_code_norm)


def get_unit_detail(turnover_id: int, today: date | None = None) -> dict | None:
    """Return a single read model for the unit-detail screen: turnover (with
    lifecycle fields), unit, tasks, readiness, sla, days_to_be_ready. All
    interpretations (lifecycle, SLA, DTBR) are computed in the service layer.
    If the turnover is open and has no tasks, repairs by generating tasks from templates."""
    detail = turnover_service.get_turnover_detail(turnover_id)
    if detail is None:
        return None
    unit_id = detail.get("unit_id")
    unit = get_unit_by_id(unit_id) if unit_id else None
    readiness = task_service.get_readiness(turnover_id)
    tasks = readiness["tasks"]
    sla = risk_service.evaluate_sla(turnover_id, today=today)
    dtbr = turnover_lifecycle.days_to_be_ready(detail, tasks, today)
    is_open = turnover_lifecycle.is_open(detail)
    return {
        "turnover": detail,
        "unit": unit,
        "tasks": tasks,
        "readiness": readiness,
        "sla": sla,
        "days_to_be_ready": dtbr,
        "is_open": is_open,
    }


def get_units(
    property_id: int,
    phase_scope: list[int] | None = None,
    *,
    active_only: bool = True,
    user_id: int = 0,
) -> list[dict]:
    """Return units for the property, optionally filtered by phase scope (operational view)."""
    if phase_scope is None:
        phase_scope = scope_service.get_phase_scope(user_id, property_id)
    return unit_repository.get_by_property(
        property_id, active_only=active_only, phase_ids=phase_scope
    )


def list_all_units_for_property(property_id: int, *, active_only: bool = True) -> list[dict]:
    """Return all units for the property (ignores phase scope). Read-only.

    Includes ``unit_code``, ``phase_name``, and ``building_name`` for grid views.
    """
    return unit_repository.list_for_property_with_structure_labels(
        property_id,
        active_only=active_only,
    )


def list_unit_master_import_units(property_id: int) -> list[dict]:
    """Return importer-written unit fields for the Unit Master Import table."""
    return unit_repository.list_unit_master_import_units(property_id)


def import_unit_master(
    property_id: int,
    df: "pd.DataFrame",
    strict: bool,
) -> dict:
    """Process Unit Master CSV rows: create units/phases/buildings.

    All writes run in a single DB transaction. Preflight validates every row
    before any mutation; any validation failure raises ``UnitMasterImportError``.
    On success returns ``{"created", "skipped", "errors": []}`` (errors always empty).
    """
    check_writes_enabled()

    preflight_errors: list[str] = []
    seen_norms: set[str] = set()

    for idx, row in df.iterrows():
        raw = str(row.get("unit_code", "")).strip()
        if not raw:
            preflight_errors.append(f"Row {idx + 2}: empty unit_code.")
            continue

        norm = raw.upper()
        if norm in seen_norms:
            preflight_errors.append(
                f"Row {idx + 2}: duplicate unit_code '{norm}' in import file."
            )
            continue
        seen_norms.add(norm)

        if unit_repository.get_by_code_norm(property_id, norm):
            continue

        if strict:
            preflight_errors.append(
                f"Row {idx + 2}: unit '{norm}' not found (strict mode)."
            )

    if preflight_errors:
        raise UnitMasterImportError(preflight_errors)

    with transaction():
        phase_cache: dict[str, dict] = {}
        for p in property_repository.get_phases(property_id):
            phase_cache[p["phase_code"]] = p

        building_cache: dict[tuple[int, str], dict] = {}
        for phase in phase_cache.values():
            for b in property_repository.get_buildings(phase["phase_id"]):
                building_cache[(phase["phase_id"], b["building_code"])] = b

        created = 0
        skipped = 0

        for idx, row in df.iterrows():
            raw = str(row.get("unit_code", "")).strip()
            if not raw:
                raise UnitMasterImportError([f"Row {idx + 2}: empty unit_code."])

            norm = raw.upper()
            existing = unit_repository.get_by_code_norm(property_id, norm)

            if existing:
                skipped += 1
                continue

            if strict:
                raise UnitMasterImportError(
                    [f"Row {idx + 2}: unit '{norm}' not found (strict mode)."]
                )

            try:
                phase_id: int | None = None
                phase_val = str(row.get("phase", "")).strip() if "phase" in df.columns else ""
                if phase_val:
                    if phase_val in phase_cache:
                        phase_id = phase_cache[phase_val]["phase_id"]
                    else:
                        new_phase = property_service.create_phase(property_id, phase_val)
                        phase_cache[phase_val] = new_phase
                        phase_id = new_phase["phase_id"]

                building_id: int | None = None
                bldg_val = str(row.get("building", "")).strip() if "building" in df.columns else ""
                if bldg_val:
                    if phase_id is None:
                        default_code = "_DEFAULT"
                        if default_code not in phase_cache:
                            default_phase = property_service.create_phase(
                                property_id, default_code, name="Default Phase",
                            )
                            phase_cache[default_code] = default_phase
                        phase_id = phase_cache[default_code]["phase_id"]

                    cache_key = (phase_id, bldg_val)
                    if cache_key in building_cache:
                        building_id = building_cache[cache_key]["building_id"]
                    else:
                        new_bldg = property_service.create_building(
                            property_id, phase_id, bldg_val,
                        )
                        building_cache[cache_key] = new_bldg
                        building_id = new_bldg["building_id"]

                floor_plan = _row_str(row, df, "Floor Plan", "floor_plan")
                gross_sq_ft = _row_int(row, df, "Gross Sq. Ft.", "gross_sq_ft")

                has_carpet = (
                    str(row.get("has_carpet", "")).strip().lower() in ("true", "1", "yes")
                    if "has_carpet" in df.columns
                    else False
                )
                has_wd = (
                    str(row.get("has_wd", "")).strip().lower() in ("true", "1", "yes")
                    if "has_wd" in df.columns
                    else False
                )

                property_service.create_unit(
                    property_id=property_id,
                    unit_code_raw=raw,
                    unit_code_norm=norm,
                    unit_identity_key=norm,
                    phase_id=phase_id,
                    building_id=building_id,
                    floor_plan=floor_plan,
                    gross_sq_ft=gross_sq_ft,
                    has_carpet=has_carpet,
                    has_wd_expected=has_wd,
                )
            except UnitMasterImportError:
                raise
            except Exception as exc:
                raise UnitMasterImportError(
                    [f"Row {idx + 2} ({norm}): {exc}"],
                ) from exc

            created += 1

    return {"created": created, "skipped": skipped, "errors": []}


def _row_str(row, df: "pd.DataFrame", *col_names: str) -> str | None:
    """Extract a trimmed string from a row, trying multiple column names."""
    for col in col_names:
        if col in df.columns:
            val = str(row.get(col, "")).strip()
            if val:
                return val
    return None


def _row_int(row, df: "pd.DataFrame", *col_names: str) -> int | None:
    """Extract an integer from a row, trying multiple column names."""
    for col in col_names:
        if col in df.columns:
            val = str(row.get(col, "")).strip().replace(",", "")
            if val:
                try:
                    return int(float(val))
                except (ValueError, TypeError):
                    pass
    return None

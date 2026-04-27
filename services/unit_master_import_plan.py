"""Read-only plan + validation for Unit Master CSV import (mirrors import_unit_master).

Does not call ``create_*`` or open write transactions. Used for dry-run reports and
pre-import gating. Behavior must stay aligned with ``import_unit_master`` in
``unit_service`` — change both when logic changes.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from db.repository import property_repository, unit_repository
from services.unit_service import _row_int, _row_str

UnitMasterAction = dict[str, Any]


def action_to_str(action: dict[str, Any]) -> str:
    """Stable string form for a single import action (JSON, sorted keys)."""
    return json.dumps(action, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _finalize_row(
    row_index: int,
    unit_code: str | None,
    status: str,
    messages: list[str],
    action_dicts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Enforce: valid → messages []; warning/error → non-empty messages; actions always str[]."""
    st = status if status in ("valid", "warning", "error") else "error"
    if st == "valid":
        msgs: list[str] = []
    else:
        msgs = [str(m) for m in messages if m is not None and str(m).strip() != ""]
        if not msgs:
            msgs = [f"({st}: no detail message)"]
    actions = [action_to_str(a) for a in action_dicts]
    return {
        "row_index": int(row_index),
        "unit_code": unit_code,
        "status": st,
        "messages": msgs,
        "actions": actions,
    }


def empty_unit_master_report() -> dict[str, Any]:
    """All top-level contract fields, zero rows; ``file_messages`` is always a list (never null)."""
    return {
        "total_rows": 0,
        "valid_rows": 0,
        "warning_rows": 0,
        "error_rows": 0,
        "file_messages": [],
        "rows": [],
        "has_blocking_errors": False,
    }


def normalize_unit_master_row(row: Any) -> dict[str, Any]:
    """Coerce an arbitrary row object into the stable API contract."""
    if not isinstance(row, dict):
        return _finalize_row(0, None, "error", ["Invalid row in report payload"], [])

    row_index = 0
    try:
        row_index = int(row.get("row_index", 0))
    except (TypeError, ValueError):
        pass

    raw_uc = row.get("unit_code")
    if raw_uc is None or (isinstance(raw_uc, str) and raw_uc == ""):
        unit_code: str | None = None
    else:
        unit_code = str(raw_uc).strip() or None

    st = str(row.get("status", "error"))
    if st not in ("valid", "warning", "error"):
        st = "error"

    raw_msgs = row.get("messages")
    if isinstance(raw_msgs, list):
        msg_list = [str(m) for m in raw_msgs if m is not None and str(m).strip() != ""]
    elif raw_msgs is None:
        msg_list = []
    else:
        msg_list = [str(raw_msgs)]

    actions_raw = row.get("actions") or []
    if not isinstance(actions_raw, list):
        actions_raw = []
    action_strs: list[str] = []
    for a in actions_raw:
        if isinstance(a, str):
            action_strs.append(a)
        elif isinstance(a, dict):
            action_strs.append(action_to_str(a))
        else:
            action_strs.append(str(a))

    if st == "valid":
        msg_list = []
    elif st in ("warning", "error") and not msg_list:
        msg_list = [f"({st}: no detail message)"]

    return {
        "row_index": row_index,
        "unit_code": unit_code,
        "status": st,
        "messages": msg_list,
        "actions": action_strs,
    }


def normalize_unit_master_report(r: Any) -> dict[str, Any]:
    """Top-level report with guaranteed keys and no null file_messages."""
    if not isinstance(r, dict):
        return empty_unit_master_report()
    file_messages = r.get("file_messages")
    if not isinstance(file_messages, list):
        fmsg: list[str] = []
    else:
        fmsg = [str(x) for x in file_messages if x is not None]
    raw_rows = r.get("rows")
    if not isinstance(raw_rows, list):
        raw_rows = []
    rows = [normalize_unit_master_row(x) for x in raw_rows]
    n_val = sum(1 for x in rows if x["status"] == "valid")
    n_warn = sum(1 for x in rows if x["status"] == "warning")
    n_err = sum(1 for x in rows if x["status"] == "error")
    total_rows = len(rows)
    return {
        "total_rows": total_rows,
        "valid_rows": n_val,
        "warning_rows": n_warn,
        "error_rows": n_err,
        "file_messages": fmsg,
        "rows": rows,
        "has_blocking_errors": n_err > 0,
    }


def build_unit_master_import_report(
    property_id: int,
    df: pd.DataFrame,
    strict: bool,
) -> dict[str, Any]:
    """Build per-row validation + simulated actions. Read-only (loads phases/buildings from DB)."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    file_messages: list[str] = []
    if len(df) == 0 and len(df.columns) > 0:
        file_messages.append("No data rows: the file has a header but no data rows.")
    if df.columns.duplicated().any():
        file_messages.append(
            "Duplicate column names detected; pandas keeps the last occurrence per name."
        )

    phase_cache: dict[str, dict] = {}
    for p in property_repository.get_phases(property_id):
        phase_cache[p["phase_code"]] = p

    building_cache: dict[tuple[int, str], dict] = {}
    for phase in phase_cache.values():
        for b in property_repository.get_buildings(phase["phase_id"]):
            building_cache[(phase["phase_id"], b["building_code"])] = b

    sim_phase_seq = 0
    sim_building_seq = 0

    def _next_sim_phase_id() -> int:
        nonlocal sim_phase_seq
        sim_phase_seq += 1
        return -sim_phase_seq

    def _next_sim_building_id() -> int:
        nonlocal sim_building_seq
        sim_building_seq += 1
        return -10000 - sim_building_seq

    rows_out: list[dict[str, Any]] = []
    seen_norms: set[str] = set()
    n_valid = n_warn = n_err = 0

    for row_index, (_, row) in enumerate(df.iterrows()):
        action_dicts: list[UnitMasterAction] = []
        raw = str(row.get("unit_code", "")).strip()

        if not raw:
            n_err += 1
            rows_out.append(
                _finalize_row(
                    row_index,
                    None,
                    "error",
                    ["Empty unit_code."],
                    action_dicts,
                )
            )
            continue

        norm = raw.upper()

        if norm in seen_norms:
            n_err += 1
            rows_out.append(
                _finalize_row(
                    row_index,
                    norm,
                    "error",
                    [f"Duplicate unit_code '{norm}' in import file (first row wins in DB)."],
                    action_dicts,
                )
            )
            continue
        seen_norms.add(norm)

        existing = unit_repository.get_by_code_norm(property_id, norm)
        if existing:
            action_dicts.append({"type": "would_skip_existing_unit", "unit_code": norm})
            n_valid += 1
            rows_out.append(_finalize_row(row_index, norm, "valid", [], action_dicts))
            continue

        if strict:
            n_err += 1
            rows_out.append(
                _finalize_row(
                    row_index,
                    norm,
                    "error",
                    [f"Unit '{norm}' not found in database (strict mode; no new units)."],
                    action_dicts,
                )
            )
            continue

        type_warnings = _gross_sq_ft_warnings_if_present(row, df)
        if type_warnings:
            status = "warning"
        else:
            status = "valid"

        phase_id: int | None = None
        resolved_phase_code: str | None = None
        phase_val = str(row.get("phase", "")).strip() if "phase" in df.columns else ""
        if phase_val:
            if phase_val in phase_cache:
                phase_id = int(phase_cache[phase_val]["phase_id"])
            else:
                new_pid = _next_sim_phase_id()
                phase_cache[phase_val] = {
                    "phase_id": new_pid,
                    "phase_code": phase_val,
                }
                phase_id = new_pid
                action_dicts.append({"type": "would_create_phase", "phase_code": phase_val})
            resolved_phase_code = phase_val

        bldg_val = str(row.get("building", "")).strip() if "building" in df.columns else ""
        if bldg_val:
            if phase_id is None:
                default_code = "_DEFAULT"
                if default_code not in phase_cache:
                    new_pid = _next_sim_phase_id()
                    phase_cache[default_code] = {
                        "phase_id": new_pid,
                        "phase_code": default_code,
                        "name": "Default Phase",
                    }
                    phase_id = new_pid
                    action_dicts.append(
                        {
                            "type": "would_create_phase",
                            "phase_code": default_code,
                            "name": "Default Phase",
                        }
                    )
                else:
                    phase_id = int(phase_cache[default_code]["phase_id"])
                resolved_phase_code = default_code

            ph_label = (
                resolved_phase_code
                if resolved_phase_code is not None
                else next(
                    (c for c, pr in phase_cache.items() if int(pr["phase_id"]) == int(phase_id)),
                    str(phase_id),
                )
            )
            cache_key = (int(phase_id), bldg_val)
            if cache_key not in building_cache:
                _ = _next_sim_building_id()
                building_cache[cache_key] = {
                    "building_id": 0,
                    "building_code": bldg_val,
                    "phase_id": phase_id,
                }
                action_dicts.append(
                    {
                        "type": "would_create_building",
                        "phase_code": ph_label,
                        "building_code": bldg_val,
                    }
                )

        attr: dict[str, Any] = {
            "floor_plan": _row_str(row, df, "Floor Plan", "floor_plan"),
            "gross_sq_ft": _row_int(row, df, "Gross Sq. Ft.", "gross_sq_ft"),
            "has_carpet": _parse_boolish(row, "has_carpet", df),
            "has_wd_expected": _parse_boolish(row, "has_wd", df),
        }
        action_dicts.append(
            {
                "type": "would_create_unit",
                "unit_code": norm,
                "unit_code_raw": raw,
                "attributes": {k: v for k, v in attr.items() if v is not None and v is not False},
            }
        )

        if status == "warning":
            n_warn += 1
        else:
            n_valid += 1

        rows_out.append(_finalize_row(row_index, norm, status, type_warnings, action_dicts))

    report = {
        "total_rows": len(rows_out),
        "valid_rows": n_valid,
        "warning_rows": n_warn,
        "error_rows": n_err,
        "file_messages": file_messages,
        "rows": rows_out,
        "has_blocking_errors": n_err > 0,
    }
    return normalize_unit_master_report(report)


def _parse_boolish(row, col: str, df: pd.DataFrame) -> bool:
    if col not in df.columns:
        return False
    return str(row.get(col, "")).strip().lower() in ("true", "1", "yes")


def _gross_sq_ft_warnings_if_present(row, df: pd.DataFrame) -> list[str]:
    """If no column yields a valid int but some cell was non-empty (mirrors _row_int order)."""
    last_bad: str | None = None
    for col in ("Gross Sq. Ft.", "gross_sq_ft"):
        if col not in df.columns:
            continue
        val = str(row.get(col, "")).strip().replace(",", "")
        if not val:
            continue
        try:
            int(float(val))
            return []
        except (ValueError, TypeError):
            last_bad = (
                f"Column {col!r} value {val!r} is not a valid integer; "
                "import will ignore it for gross square feet (same as current import)."
            )
    return [last_bad] if last_bad else []

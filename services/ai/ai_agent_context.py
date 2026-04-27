"""Context builder for the DMRB AI Agent.

Assembles a single read-only board/risk snapshot per chat turn.
All data comes from existing board and risk services using one shared board load.
"""

from __future__ import annotations

from datetime import date

from services import board_service, property_service, risk_service, scope_service

_TOP_N = 10


def build_context(property_id: int, today: date | None = None, user_id: int = 0) -> str:
    """Return a compact markdown snapshot of the current board state.

    One board load per call; all derived signals share that load.
    Callers should wrap in try/except — any DB failure propagates up.
    """
    today = today or date.today()

    # ── Single board load ─────────────────────────────────────────────────────
    phase_scope = scope_service.get_phase_scope(user_id, property_id)
    board = board_service.get_board_view(
        property_id, today=today, phase_scope=phase_scope, user_id=user_id
    )

    # ── Property name ─────────────────────────────────────────────────────────
    props = property_service.get_all_properties()
    property_name = next(
        (p["name"] for p in props if p["property_id"] == property_id),
        f"Property {property_id}",
    )

    # ── Derived signals (all pass board= to avoid re-loading) ─────────────────
    metrics = board_service.get_board_metrics(board=board)
    summary = board_service.get_board_summary(property_id, board=board)
    flags = board_service.get_flag_counts(property_id, board=board)
    stalled_all = board_service.work_stalled_unit_entries(board)
    stalled = stalled_all[:_TOP_N]

    risk_rows_all = risk_service.get_risk_dashboard(
        property_id, today=today, phase_scope=phase_scope, board=board, user_id=user_id
    )
    risk_rows_sorted = sorted(risk_rows_all, key=lambda r: r["risk_score"], reverse=True)
    risk_rows = risk_rows_sorted[:_TOP_N]

    # ── Format ────────────────────────────────────────────────────────────────
    lines: list[str] = []

    lines.append(f"## DMRB Board Snapshot — {property_name} — as of {today}")
    lines.append("_Authoritative for numeric answers. Do not invent values not present here._")
    lines.append("")

    lines.append("### Metrics")
    lines.append(
        f"Active: {metrics['active']} | "
        f"SLA breach: {metrics['sla_breach']} | "
        f"Move-in risk: {metrics['move_in_risk']} | "
        f"Violations: {metrics['violations']} | "
        f"Plan breach: {metrics['plan_breach']} | "
        f"Work stalled: {metrics['work_stalled']}"
    )
    lines.append("")

    by_p = summary["by_priority"]
    by_r = summary["by_readiness"]
    lines.append(f"### Board Summary (total: {summary['total']})")
    priority_str = ", ".join(f"{k}: {v}" for k, v in by_p.items() if v > 0)
    readiness_str = ", ".join(f"{k}: {v}" for k, v in by_r.items() if v > 0)
    lines.append(f"Priority — {priority_str or 'none'}")
    lines.append(f"Readiness — {readiness_str or 'none'}")
    lines.append("")

    lines.append("### Top Flags")
    lines.append(
        f"SLA_BREACH: {flags['SLA_BREACH']} | "
        f"MOVE_IN_DANGER: {flags['MOVE_IN_DANGER']} | "
        f"PLAN_BLOCKED: {flags['PLAN_BLOCKED']} | "
        f"INSPECTION_BREACH: {flags['INSPECTION_BREACH']}"
    )
    lines.append("")

    lines.append(f"### High-Risk Units (top {len(risk_rows)}, of {len(risk_rows_all)} scored)")
    if risk_rows:
        lines.append("| Unit | Phase | Score | Level | Reasons | Move-in |")
        lines.append("|------|-------|-------|-------|---------|---------|")
        for r in risk_rows:
            reasons = "; ".join(r["risk_reasons"]) if r["risk_reasons"] else "—"
            move_in = str(r["move_in_date"]) if r["move_in_date"] else "—"
            lines.append(
                f"| {r['unit_code']} | {r['phase_code']} | {r['risk_score']} "
                f"| {r['risk_level']} | {reasons} | {move_in} |"
            )
    else:
        lines.append("_No scored units._")
    lines.append("")

    lines.append(f"### Stalled Work (top {len(stalled)}, of {len(stalled_all)} units)")
    if stalled:
        for s in stalled:
            lines.append(f"Unit {s['unit_code']} — DV {s['dv']}d")
    else:
        lines.append("_No stalled units._")

    return "\n".join(lines)

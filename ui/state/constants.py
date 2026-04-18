"""Centralized UI constants — single source of truth for dropdown values,
status mappings, and display labels.  Screens import from here instead of
defining locally.
"""

from __future__ import annotations


# ── Execution Status ─────────────────────────────────────────────────────────

EXEC_MAP: dict[str, str] = {
    "NOT_STARTED": "Not Started",
    "SCHEDULED":   "Scheduled",
    "IN_PROGRESS": "In Progress",
    "COMPLETED":   "Completed",
}

EXEC_REV: dict[str, str] = {v: k for k, v in EXEC_MAP.items()}
# UI-only labels resolve to COMPLETED in the engine
EXEC_REV["N/A"] = "COMPLETED"
EXEC_REV["Canceled"] = "COMPLETED"

EXEC_LABELS: list[str] = [
    "Not Started", "Scheduled", "In Progress", "Completed",
]

EXEC_LABELS_EXTENDED: list[str] = [
    "Not Started", "Scheduled", "In Progress", "Completed", "N/A", "Canceled",
]

# Side-effect overrides applied when the user picks an extended label
EXEC_SIDE_EFFECTS: dict[str, dict[str, bool]] = {
    "N/A":      {"required": False},
    "Canceled": {"required": False, "blocking": False},
}


# ── Blocking Reasons ─────────────────────────────────────────────────────────

BLOCK_OPTIONS: list[str] = [
    "Not Blocking", "—", "Key Delivery", "Vendor Delay",
    "Parts on Order", "Permit Required", "Other",
]


# ── Turnover Status ─────────────────────────────────────────────────────────

STATUS_OPTIONS: list[str] = [
    "Vacant ready", "Vacant not ready", "On notice",
]


# ── Board Filters ────────────────────────────────────────────────────────────

NVM_OPTS: list[str] = ["All", "Notice", "Notice + SMI", "Vacant", "SMI", "Move-In"]

QC_OPTS: list[str] = ["All", "QC Done", "QC Not done"]

BRIDGE_OPTS: list[str] = [
    "All", "Insp Breach", "SLA Breach", "SLA MI Breach", "Plan Breach",
]

VALUE_OPTS: list[str] = ["All", "Yes", "No"]


# ── Task Types ───────────────────────────────────────────────────────────────

TASK_DISPLAY: dict[str, str] = {
    "INSPECT":          "Inspection",
    "CARPET_BID":       "Carpet Bid",
    "MAKE_READY_BID":   "Make Ready Bid",
    "PAINT":            "Paint",
    "MAKE_READY":       "Make Ready",
    "HOUSEKEEPING":     "Housekeeping",
    "CARPET_CLEAN":     "Carpet Clean",
    "FINAL_WALK":       "Final Walk",
    "QUALITY_CONTROL":  "Quality Control",
    # Legacy mappings for backward compat with existing demo data
    "CARPET":           "Carpet",
    "CLEAN":            "Cleaning",
    "APPLIANCE_CHECK":  "Appliance Check",
}

TASK_COLS: list[str] = [
    "INSPECT", "CARPET_BID", "MAKE_READY_BID", "PAINT", "MAKE_READY",
    "HOUSEKEEPING", "CARPET_CLEAN", "FINAL_WALK", "QUALITY_CONTROL",
]

# Canonical pipeline display order — use this wherever task sequence matters.
TASK_PIPELINE_ORDER: list[str] = list(TASK_COLS)


# ── Carpet Status ────────────────────────────────────────────────────────────

CARPET_STATUSES: list[str] = ["Carpet", "No Carpet", "Carpet Replacement"]

CARPET_ICONS: dict[str, str] = {
    "Carpet":             "🟢",
    "No Carpet":          "⚪",
    "Carpet Replacement": "🔶",
}


# ── W/D Options ──────────────────────────────────────────────────────────────

WD_OPTS: list[str] = ["No", "Yes", "Yes stack"]

WD_NO_REASONS: list[str] = [
    "Not applicable", "Tenant owns", "Shared laundry", "On order", "Other",
]


# ── Notes ────────────────────────────────────────────────────────────────────

NOTE_SEVERITIES: list[str] = ["INFO", "WARNING", "CRITICAL"]

SEVERITY_ICONS: dict[str, str] = {
    "INFO":     "ℹ️",
    "WARNING":  "⚠️",
    "CRITICAL": "🚨",
}


# ── Admin ────────────────────────────────────────────────────────────────────

OFFSET_OPTS: list[int] = list(range(1, 11))


# ── Risk Levels ──────────────────────────────────────────────────────────────

RISK_LEVELS: list[str] = ["HIGH", "MEDIUM", "LOW"]

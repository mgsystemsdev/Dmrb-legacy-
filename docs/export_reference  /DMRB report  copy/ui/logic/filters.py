# filters.py

import pandas as pd

# =================================================
# Shared Definitions
# =================================================

STATUS_GROUPS = {
    "All": ["vacant ready", "vacant not ready", "on notice"],
    "Vacant": ["vacant ready", "vacant not ready"],
    "Vacant Ready": ["vacant ready"],
    "Vacant Not Ready": ["vacant not ready"],
    "On Notice": ["on notice"],
}


# =================================================
# Filters
# =================================================

def filter_by_phase(df: pd.DataFrame, phase):
    if phase == "All":
        return df
    return df[df["P"] == phase]


def filter_by_status(df: pd.DataFrame, status_group):
    allowed = STATUS_GROUPS.get(status_group, [])
    return df[df["Status_Norm"].isin(allowed)]


def filter_by_nvm(df: pd.DataFrame, nvm):
    if nvm == "All":
        return df
    return df[df["N/V/M"] == nvm]


BREACH_MAP = {
    "All": None,
    "Any Breach": ["Inspection_SLA_Breach", "SLA_Breach", "SLA_MoveIn_Breach", "Plan_Breach"],
    "SLA Move-In Breach": "SLA_MoveIn_Breach",
    "SLA Breach": "SLA_Breach",
    "Plan Bridge": "Plan_Breach",
    "Inspection Breach": "Inspection_SLA_Breach",
}


def filter_by_breach(df: pd.DataFrame, breach_selection: str):
    if breach_selection == "All":
        return df
    target = BREACH_MAP.get(breach_selection)
    if isinstance(target, list):
        mask = df[target].any(axis=1)
        return df[mask]
    if target and target in df.columns:
        return df[df[target] == True]
    return df


# =================================================
# Sorting
# =================================================

def sort_by_movein_then_dv(df: pd.DataFrame):
    df = df.copy()

    df["Move_in_dt"] = pd.to_datetime(df["Move_in"], errors="coerce")

    df["_has_movein"] = df["Move_in_dt"].notna()

    df = df.sort_values(
        by=["_has_movein", "Move_in_dt", "DV"],
        ascending=[False, True, False],
    )

    return df.drop(columns=["_has_movein"])


# =================================================
# Normalization
# =================================================

def normalize_excel_dates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    date_cols = [
        "Move_in", "Move_out", "Ready_Date",
        "Insp", "Paint", "MR", "HK", "CC"
    ]

    for col in date_cols:
        if col not in df.columns:
            continue
        # Try plain datetime parse first (already converted by enrichment)
        parsed = pd.to_datetime(df[col], errors="coerce")
        # If mostly NaT, try Excel serial number format
        if parsed.notna().sum() == 0:
            parsed = pd.to_datetime(
                pd.to_numeric(df[col], errors="coerce"),
                origin="1899-12-30",
                unit="D",
                errors="coerce",
            )
        df[col] = parsed.dt.strftime("%m/%d/%Y").fillna("")

    return df

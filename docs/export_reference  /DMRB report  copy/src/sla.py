import pandas as pd
import numpy as np
from datetime import date

# ============================================================
# SLA CONFIGURATION
# ============================================================

INSPECTION_SLA_DAYS = 1       # Inspection must occur within 1 business day
TURN_SLA_DAYS = 10            # Unit must be ready within 10 business days
MOVE_IN_BUFFER_DAYS = 2       # Must be ready 2 days before move-in

# ============================================================
# STAGE 3 — SLA ENGINE
# ============================================================

def run_sla(df: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    """
    Enforces SLA and plan compliance.
    Input:  Stage 2 DataFrame (intelligence)
    Output: Stage 3 DataFrame (sla + risk flags)
    """

    if today is None:
        today = date.today()

    df = df.copy()

    # --------------------------------------------------------
    # Days to Move-In (helper metric)
    # --------------------------------------------------------
    def calc_days_to_move_in(move_in):
        if move_in == "" or pd.isna(move_in):
            return np.nan
        try:
            move_in_date = pd.to_datetime(move_in, errors="coerce")
            if pd.isna(move_in_date):
                return np.nan
            return (move_in_date.date() - today).days
        except Exception:
            return np.nan

    df["Days_To_MoveIn"] = df["Move_in"].apply(calc_days_to_move_in)

    # --------------------------------------------------------
    # Inspection SLA Breach
    # --------------------------------------------------------
    # Inspection not completed within 1 business day after move-out
    df["Inspection_SLA_Breach"] = (
        df["Is_Vacant"] &
        (df["Insp_status"].astype(str).str.upper() != "DONE") &
        (df["Aging_Business_Days"] > INSPECTION_SLA_DAYS)
    )

    # --------------------------------------------------------
    # Global Turn SLA Breach
    # --------------------------------------------------------
    # Unit still vacant and not ready after 10 business days
    df["SLA_Breach"] = (
        df["Is_Vacant"] &
        (~df["Is_Unit_Ready"]) &
        (df["Aging_Business_Days"] > TURN_SLA_DAYS)
    )

    # --------------------------------------------------------
    # Move-In SLA Breach
    # --------------------------------------------------------
    # Move-in is imminent but unit cannot meet it
    df["SLA_MoveIn_Breach"] = (
        df["Is_MoveIn_Present"] &
        (~df["Is_Unit_Ready_For_Moving"]) &
        (df["Days_To_MoveIn"] <= MOVE_IN_BUFFER_DAYS) &
        (df["Days_To_MoveIn"] >= 0)
    )

    # --------------------------------------------------------
    # Plan Breach
    # --------------------------------------------------------
    # Declared Ready_Date has passed but unit is not actually ready
    def calc_plan_breach(r):
        if not r["Is_Ready_Declared"]:
            return False
        try:
            ready_date = pd.to_datetime(r["Ready_Date"], errors="coerce")
            if pd.isna(ready_date):
                return False
            if today >= ready_date.date():
                return not r["Is_Unit_Ready"]
            return False
        except Exception:
            return False

    df["Plan_Breach"] = df.apply(calc_plan_breach, axis=1)

    # --------------------------------------------------------
    # Sorting (preserve operational priority)
    # --------------------------------------------------------
    df = df.sort_values(
        by="Aging_Business_Days",
        ascending=False,
        na_position="last"
    )

    return df

import pandas as pd

# ============================================================
# STAGE 2 — OPERATIONAL INTELLIGENCE
# ============================================================

def run_intelligence(df: pd.DataFrame) -> pd.DataFrame:
    """
    Interprets Core Facts into operational meaning.
    Input:  Stage 1 DataFrame (facts)
    Output: Stage 2 DataFrame (intelligence)
    """

    df = df.copy()

    # --------------------------------------------------------
    # Status normalization (for filtering / UI use)
    # --------------------------------------------------------
    df["Status_Norm"] = (
        df["Status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    # --------------------------------------------------------
    # Readiness flags
    # --------------------------------------------------------
    df["Is_Unit_Ready"] = (
        df["Status"].astype(str).str.upper().eq("VACANT READY") &
        (df["Task_State"] == "All Tasks Complete")
    )

    df["Is_Unit_Ready_For_Moving"] = (
        df["Is_Unit_Ready"] &
        df["Is_MoveIn_Present"] &
        df["Is_QC_Done"]
    )

    # --------------------------------------------------------
    # Turn execution flag
    # --------------------------------------------------------
    df["In_Turn_Execution"] = (
        df["Is_Vacant"] &
        (~df["Is_Unit_Ready"])
    )

    # --------------------------------------------------------
    # Move-In happened flag
    # --------------------------------------------------------
    today = pd.Timestamp.today().normalize()

    df["Move_In_Happened"] = (
        df["Move_in"].ne("") &
        (pd.to_datetime(df["Move_in"], errors="coerce") <= today)
    )

    # --------------------------------------------------------
    # Operational State (core business logic)
    # --------------------------------------------------------
    def operational_state(r):
        # NOTICE logic
        if r["Is_On_Notice"]:
            if r["Is_SMI"]:
                return "On Notice - Scheduled"
            return "On Notice"

        # Out of scope
        if not (r["Is_Vacant"] or r["Is_SMI"]):
            return "Out of Scope"

        # Vacant / SMI logic
        if (
            r["Is_MoveIn_Present"]
            and not r["Is_Unit_Ready_For_Moving"]
            and r["In_Turn_Execution"]
        ):
            return "Move-In Risk"

        if r["Is_Unit_Ready"] and r["Is_MoveIn_Present"] and not r["Is_QC_Done"]:
            return "QC Hold"

        if r["Is_Task_Stalled"]:
            return "Work Stalled"

        if r["Task_State"] == "In Progress":
            return "In Progress"

        if r["Is_Unit_Ready"]:
            return "Apartment Ready"

        return "Pending Start"

    df["Operational_State"] = df.apply(operational_state, axis=1)

    # --------------------------------------------------------
    # Prevention Risk Flag
    # --------------------------------------------------------
    df["Prevention_Risk_Flag"] = (
        df["In_Turn_Execution"] & (
            df["Note_Category"].isin(["HOLD", "ISSUE", "REOPEN", "MAYBE"]) |
            (~df["Has_Assignment"]) |
            (
                (df["Task_State"] == "In Progress") &
                (~df["Is_Task_Stalled"])
            )
        )
    )

    # --------------------------------------------------------
    # Attention Badge (human-facing signal)
    # --------------------------------------------------------
    def attention_badge(r):
        # Move-In already happened (highest priority)
        if r["Move_In_Happened"]:
            return "📦 Apartment Move-In"

        # NOTICE units
        if r["Is_On_Notice"]:
            if r["Is_SMI"]:
                return "📋 On Notice - Scheduled"
            return "📋 On Notice"

        # SMI with move-in scheduled
        if r["Is_SMI"] and r["Is_MoveIn_Present"]:
            return "📅 Scheduled to Move In"

        base_map = {
            "Out of Scope": "Out of Scope",
            "Move-In Risk": "🔴 Move-In Risk",
            "QC Hold": "🚫 QC Hold",
            "Work Stalled": "⏸️ Work Stalled",
            "In Progress": "🔧 In Progress",
            "Pending Start": "⏳ Pending Start",
            "Apartment Ready": "🟢 Apartment Ready",
        }

        base = base_map.get(r["Operational_State"], "")

        if (
            r["Operational_State"] in {"Pending Start", "In Progress"}
            and r["Prevention_Risk_Flag"]
        ):
            return "🟡 Needs Attention"

        return base

    df["Attention_Badge"] = df.apply(attention_badge, axis=1)

    # --------------------------------------------------------
    # Sorting (maintain operational priority)
    # --------------------------------------------------------
    df = df.sort_values(
        by="Aging_Business_Days",
        ascending=False,
        na_position="last"
    )

    return df

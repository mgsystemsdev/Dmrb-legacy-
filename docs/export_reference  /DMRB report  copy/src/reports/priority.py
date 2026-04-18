import pandas as pd
import numpy as np


def build_priority_report(df: pd.DataFrame, top_n: int = 20) -> list[dict]:
    df = df.copy()

    df["Priority_Score"] = 0
    df.loc[df["SLA_Breach"], "Priority_Score"] += 50
    df.loc[df["SLA_MoveIn_Breach"], "Priority_Score"] += 40
    df.loc[df["Is_Task_Stalled"], "Priority_Score"] += 30
    df.loc[df["Aging_Business_Days"] >= 8, "Priority_Score"] += 20
    df.loc[df["Has_Note_Context"], "Priority_Score"] += 10

    vacant_mask = df["Status"].fillna("").astype(str).str.strip().str.lower().str.startswith("vacant")
    top_units = df[vacant_mask].nlargest(top_n, "Priority_Score")

    def build_flags(r):
        flags = []
        if r["SLA_Breach"]:
            flags.append("SLA BREACH")
        if r["SLA_MoveIn_Breach"]:
            flags.append("MOVE-IN RISK")
        if r["Is_Task_Stalled"]:
            flags.append("STALLED")
        if r["Has_Note_Context"]:
            flags.append(r["Note_Category"])
        return " | ".join(flags) if flags else ""

    def build_action(r):
        if r["SLA_Breach"]:
            return "ESCALATE - Already in breach, needs immediate resolution"
        if r["SLA_MoveIn_Breach"]:
            dtm = r["Days_To_MoveIn"]
            days_str = f"{dtm:.0f}" if pd.notna(dtm) else "?"
            return f"URGENT - Move-in {days_str} days away, unit not ready"
        if r["Is_Task_Stalled"]:
            return "REVIEW - Task stalled, investigate blockers"
        return "MONITOR - Track progress closely"

    top_units["Alerts"] = top_units.apply(build_flags, axis=1)
    top_units["Action"] = top_units.apply(build_action, axis=1)

    top_units = top_units.reset_index(drop=True)

    view = top_units[[
        "P", "Unit", "Priority_Score", "Aging_Business_Days",
        "Operational_State", "Task_Completion_Ratio",
        "Table_Current_Task", "Alerts", "Action",
    ]].copy()

    view = view.rename(columns={
        "P": "Phase",
        "Priority_Score": "Priority",
        "Aging_Business_Days": "Days Vacant",
        "Operational_State": "Status",
        "Task_Completion_Ratio": "Progress %",
        "Table_Current_Task": "Current Task",
    })

    view["Phase"] = pd.to_numeric(view["Phase"], errors="coerce")

    results = []

    score_df = pd.DataFrame({
        "Condition": [
            "SLA Breach",
            "Move-In Risk",
            "Task Stalled",
            "Aging >= 8 days",
            "Has Notes/Issues",
        ],
        "Points": [50, 40, 30, 20, 10],
    })

    results.append({
        "title": "Priority Scoring",
        "table_name": "PriorityScoring",
        "df": score_df,
    })

    results.append({
        "title": f"Top {len(view)} Priority Units",
        "table_name": "TopPriorityUnits",
        "df": view,
    })

    return results

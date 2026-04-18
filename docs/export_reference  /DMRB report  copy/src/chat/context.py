"""
Data context builder for Ops Assistant.

Builds the operational summary, CSV data, daily stats,
and trend analysis for injection into the system prompt.
"""

import pandas as pd
import numpy as np
from datetime import date

from chat.memory import get_snapshot_history, save_daily_snapshot


# --------------------------------------------------
# Daily stats (stored as snapshot for trend tracking)
# --------------------------------------------------

def compute_daily_stats(df: pd.DataFrame) -> dict:
    stats = {"total_units": len(df)}

    if "Is_Vacant" in df.columns:
        stats["vacant_count"] = int(df["Is_Vacant"].sum())
    if "Is_Unit_Ready" in df.columns:
        stats["ready_count"] = int(df["Is_Unit_Ready"].sum())
    if "Operational_State" in df.columns:
        stats["stalled_count"] = int((df["Operational_State"] == "Work Stalled").sum())

    breach_count = 0
    for col in ["SLA_MoveIn_Breach", "SLA_Breach", "Plan_Breach", "Inspection_SLA_Breach"]:
        if col in df.columns:
            breach_count += int(df[col].sum() if df[col].dtype == bool else (df[col] == True).sum())
    stats["breach_count"] = breach_count

    if "Aging_Business_Days" in df.columns:
        avg = df["Aging_Business_Days"].mean()
        stats["avg_aging"] = round(float(avg), 1) if pd.notna(avg) else 0

    # State distribution
    if "Operational_State" in df.columns:
        stats["state_distribution"] = df["Operational_State"].value_counts().to_dict()

    # Workload by assignee
    if "Assign" in df.columns:
        stats["workload"] = df["Assign"].value_counts().to_dict()

    return stats


def store_daily_snapshot(df: pd.DataFrame):
    stats = compute_daily_stats(df)
    save_daily_snapshot(stats)


# --------------------------------------------------
# Trend analysis (compare today vs history)
# --------------------------------------------------

def build_trend_summary() -> str:
    history = get_snapshot_history(days=14)
    if len(history) < 2:
        return ""

    today = history[0]
    yesterday = history[1] if len(history) > 1 else None
    week_ago = history[6] if len(history) > 6 else None

    lines = ["\n## Operational Trends\n"]

    def _compare(label, key, current, previous, label_period):
        if previous is None:
            return
        curr = current.get(key, 0) or 0
        prev = previous.get(key, 0) or 0
        if prev == 0:
            return
        delta = curr - prev
        pct = round((delta / prev) * 100, 1) if prev else 0
        arrow = "📈" if delta > 0 else "📉" if delta < 0 else "➡️"
        lines.append(f"- {label}: {curr} today vs {prev} {label_period} ({arrow} {delta:+d}, {pct:+.1f}%)")

    if yesterday:
        lines.append("**vs Yesterday:**")
        _compare("Vacant units", "vacant_count", today, yesterday, "yesterday")
        _compare("Stalled units", "stalled_count", today, yesterday, "yesterday")
        _compare("Total breaches", "breach_count", today, yesterday, "yesterday")
        _compare("Ready units", "ready_count", today, yesterday, "yesterday")
        if today.get("avg_aging") and yesterday.get("avg_aging"):
            lines.append(f"- Avg aging: {today['avg_aging']} days vs {yesterday['avg_aging']} days")

    if week_ago:
        lines.append("\n**vs 7 Days Ago:**")
        _compare("Vacant units", "vacant_count", today, week_ago, "7d ago")
        _compare("Stalled units", "stalled_count", today, week_ago, "7d ago")
        _compare("Total breaches", "breach_count", today, week_ago, "7d ago")

    return "\n".join(lines) if len(lines) > 1 else ""


# --------------------------------------------------
# Operational summary (injected into system prompt)
# --------------------------------------------------

def build_operational_summary(df: pd.DataFrame) -> str:
    lines = ["## Operational Snapshot (as of today)\n"]

    total = len(df)
    lines.append(f"**Total units in dataset:** {total}")

    if "Operational_State" in df.columns:
        state_counts = df["Operational_State"].value_counts()
        lines.append("\n**Units by Operational State:**")
        for state, count in state_counts.items():
            lines.append(f"  - {state}: {count}")

    breach_cols = {
        "SLA_MoveIn_Breach": "🔴 Move-In SLA Breach",
        "SLA_Breach":        "🟠 SLA Breach (10+ days)",
        "Plan_Breach":       "🟡 Plan Breach",
        "Inspection_SLA_Breach": "⚠️ Inspection SLA Breach",
    }
    lines.append("\n**SLA & Breach Flags:**")
    for col, label in breach_cols.items():
        if col in df.columns:
            n = df[col].sum() if df[col].dtype == bool else (df[col] == True).sum()
            lines.append(f"  - {label}: {int(n)} units")

    if "Note_Category" in df.columns:
        issues = (df["Note_Category"] == "ISSUE").sum()
        holds = (df["Note_Category"] == "HOLD").sum()
        lines.append(f"\n**Active Notes:** {int(issues)} ISSUE, {int(holds)} HOLD")
        if issues > 0:
            units = df[df["Note_Category"] == "ISSUE"]["Unit"].tolist()
            lines.append(f"  - ISSUE units: {', '.join(str(u) for u in units)}")
        if holds > 0:
            units = df[df["Note_Category"] == "HOLD"]["Unit"].tolist()
            lines.append(f"  - HOLD units: {', '.join(str(u) for u in units)}")

    if "Days_To_MoveIn" in df.columns:
        df_mi = df.copy()
        df_mi["Days_To_MoveIn"] = pd.to_numeric(df_mi["Days_To_MoveIn"], errors="coerce")
        soon = df_mi[(df_mi["Days_To_MoveIn"] >= 0) & (df_mi["Days_To_MoveIn"] <= 3)]
        lines.append(f"\n**Move-ins in next 3 days:** {len(soon)} units")
        for _, row in soon.iterrows():
            dtm = int(row["Days_To_MoveIn"])
            ready = "✅ Ready" if row.get("Is_Unit_Ready", False) else "❌ NOT READY"
            lines.append(f"  - {row['Unit']} | Day {dtm} | {ready} | Assigned: {row.get('Assign','?')}")

    if "Operational_State" in df.columns:
        stalled = df[df["Operational_State"] == "Work Stalled"]
        lines.append(f"\n**Stalled units:** {len(stalled)}")
        for _, row in stalled.iterrows():
            lines.append(f"  - {row['Unit']} | Task: {row.get('Table_Current_Task','?')} | Assigned: {row.get('Assign','?')}")

    if "Assign" in df.columns and "Operational_State" in df.columns:
        active_states = ["In Progress", "Work Stalled", "Pending Start"]
        active = df[df["Operational_State"].isin(active_states)]
        assignees = ["Miguel G", "Michael", "Brad", "Total"]
        lines.append("\n**Workload by assignee:**")
        for name in assignees:
            count = (active["Assign"].str.strip() == name).sum()
            breach = 0
            for bcol in ["SLA_MoveIn_Breach", "SLA_Breach", "Plan_Breach"]:
                if bcol in df.columns:
                    breach += int(((df["Assign"].str.strip() == name) & (df[bcol] == True)).sum())
            label = f"{name} (company)" if name == "Total" else name
            lines.append(f"  - {label}: {int(count)} active | {breach} breaches")

    if "DV" in df.columns and "Is_SMI" in df.columns:
        df_dv = df.copy()
        df_dv["DV"] = pd.to_numeric(df_dv["DV"], errors="coerce")
        long_v = df_dv[(df_dv["DV"] > 60) & (df_dv["Is_SMI"] == False) & (df_dv["Is_On_Notice"] == False)]
        lines.append(f"\n**Long vacancies (60+ days, no move-in):** {len(long_v)} units")

    return "\n".join(lines)


# --------------------------------------------------
# Data CSV for full context injection (trimmed columns for token efficiency)
# --------------------------------------------------

CHAT_COLUMNS = [
    "Unit", "Assign", "Status", "N/V/M",
    "Operational_State", "Attention_Badge", "Task_State", "Task_Completion_Ratio",
    "Table_Current_Task", "Table_Next_Task", "Is_Task_Stalled",
    "Aging_Business_Days", "Days_To_MoveIn", "DV", "DTBR",
    "Move_out", "Ready_Date", "Move_in",
    "Insp_status", "Paint_status", "MR_Status", "HK_Status", "CC_status",
    "Is_Vacant", "Is_SMI", "Is_On_Notice", "Is_Unit_Ready", "Is_Unit_Ready_For_Moving",
    "In_Turn_Execution", "Has_Assignment", "Is_QC_Done",
    "SLA_MoveIn_Breach", "SLA_Breach", "Plan_Breach", "Inspection_SLA_Breach",
    "Note_Text", "Note_Category", "Prevention_Risk_Flag",
]


def build_data_csv(df: pd.DataFrame) -> str:
    use_cols = [c for c in CHAT_COLUMNS if c in df.columns]
    display = df[use_cols].copy() if use_cols else df.copy()

    date_cols = ["Move_out", "Ready_Date", "Move_in", "Insp", "Paint", "MR", "HK", "CC"]
    for col in date_cols:
        if col in display.columns:
            display[col] = pd.to_datetime(display[col], errors="coerce").dt.strftime("%m/%d/%Y").fillna("")

    for col in display.select_dtypes(include=["bool"]).columns:
        display[col] = display[col].map({True: "Yes", False: "No"})

    return display.to_csv(index=False)

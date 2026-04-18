import pandas as pd
import numpy as np
from datetime import date


def build_daily_ops_report(df: pd.DataFrame, total_portfolio: int = 0, today: date | None = None) -> list[dict]:
    if today is None:
        today = date.today()

    results = []

    total_units = total_portfolio if total_portfolio > 0 else len(df)
    vacant_mask = df["Status"].fillna("").astype(str).str.strip().str.lower().str.startswith("vacant")
    vacant_units = vacant_mask.sum()
    vacancy_rate = (vacant_units / total_units * 100) if total_units > 0 else 0

    results.append({
        "title": f"Portfolio Overview — {today.strftime('%A, %B %d, %Y')}",
        "table_name": "PortfolioOverview",
        "df": pd.DataFrame({
            "Metric": [
                "Total Units",
                "Vacant Units",
                "Occupied Units",
                "Vacancy Rate",
            ],
            "Value": [
                total_units,
                vacant_units,
                total_units - vacant_units,
                f"{vacancy_rate:.1f}%",
            ],
        }),
    })

    vacant_df = df[df["Is_Vacant"] == True]
    aging = vacant_df["Aging_Business_Days"]
    avg_turn = aging.mean() if len(aging) > 0 else 0
    median_turn = aging.median() if len(aging) > 0 else 0
    max_turn = aging.max() if len(aging) > 0 else 0

    results.append({
        "title": "Turn Performance",
        "table_name": "TurnPerformance",
        "df": pd.DataFrame({
            "Metric": [
                "Average Turn Time",
                "Median Turn Time",
                "Longest Turn",
            ],
            "Value": [
                f"{avg_turn:.1f} days",
                f"{median_turn:.1f} days",
                f"{max_turn:.0f} days" if pd.notna(max_turn) else "—",
            ],
        }),
    })

    total_breaches = df["SLA_Breach"].sum()
    inspection_breaches = df["Inspection_SLA_Breach"].sum()
    movein_breaches = df["SLA_MoveIn_Breach"].sum()
    plan_breaches = df["Plan_Breach"].sum()
    compliance_rate = (
        (vacant_units - total_breaches) / vacant_units * 100
        if vacant_units > 0
        else 100
    )

    results.append({
        "title": "SLA Compliance",
        "table_name": "SLACompliance",
        "df": pd.DataFrame({
            "Metric": [
                "Turn SLA Breaches",
                "Inspection SLA Breaches",
                "Move-In Risk",
                "Plan Breaches",
                "Compliance Rate",
            ],
            "Value": [
                int(total_breaches),
                int(inspection_breaches),
                int(movein_breaches),
                int(plan_breaches),
                f"{compliance_rate:.1f}%",
            ],
        }),
    })

    status_counts = df["Operational_State"].value_counts()
    op_metrics = []
    op_values = []
    for status, count in status_counts.items():
        pct = (count / len(df)) * 100
        op_metrics.append(status)
        op_values.append(f"{count} ({pct:.1f}%)")

    results.append({
        "title": "Operational Status",
        "table_name": "OperationalStatus",
        "df": pd.DataFrame({
            "State": op_metrics,
            "Units": op_values,
        }),
    })

    in_progress = df[df["In_Turn_Execution"] == True]
    avg_completion = in_progress["Task_Completion_Ratio"].mean() if len(in_progress) > 0 else 0
    stalled = int(df["Is_Task_Stalled"].sum())

    results.append({
        "title": "Work In Progress",
        "table_name": "WorkInProgress",
        "df": pd.DataFrame({
            "Metric": [
                "Units in Active Turn",
                "Avg Completion",
                "Stalled Tasks",
            ],
            "Value": [
                len(in_progress),
                f"{avg_completion:.1f}%",
                stalled,
            ],
        }),
    })

    ready = int(df["Is_Unit_Ready"].sum())
    ready_for_moving = int(df["Is_Unit_Ready_For_Moving"].sum())

    results.append({
        "title": "Ready For Move-In",
        "table_name": "ReadyForMoveIn",
        "df": pd.DataFrame({
            "Metric": [
                "Units Ready",
                "Units QC Complete",
                "Awaiting QC",
            ],
            "Value": [
                ready,
                ready_for_moving,
                ready - ready_for_moving,
            ],
        }),
    })

    at_risk = df[
        (df["Is_Vacant"])
        & (~df["Is_Unit_Ready"])
        & (df["Aging_Business_Days"] >= 8)
        & (df["Aging_Business_Days"] < 10)
    ]

    alerts = []
    if len(at_risk) > 0:
        alerts.append((f"{len(at_risk)} units at risk of SLA breach (8-9 days)", "Warning"))
    if total_breaches > 0:
        alerts.append((f"{int(total_breaches)} units currently in SLA breach", "Critical"))
    if movein_breaches > 0:
        alerts.append((f"{int(movein_breaches)} units at risk of missing move-in", "Critical"))
    if stalled > 0:
        alerts.append((f"{stalled} units with stalled tasks", "Warning"))
    if not alerts:
        alerts.append(("No critical alerts — operations running smoothly", "OK"))

    results.append({
        "title": "Critical Alerts",
        "table_name": "CriticalAlerts",
        "df": pd.DataFrame({
            "Alert": [a[0] for a in alerts],
            "Severity": [a[1] for a in alerts],
        }),
    })

    return results

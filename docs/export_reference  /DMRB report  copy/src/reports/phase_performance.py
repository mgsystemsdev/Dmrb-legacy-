import pandas as pd
import numpy as np


def build_phase_performance(df: pd.DataFrame, total_portfolio: int = 0) -> list[dict]:
    df = df.copy()
    total_units = total_portfolio if total_portfolio > 0 else len(df)
    df["Phase"] = pd.to_numeric(df["P"], errors="coerce")

    phase_stats = df.groupby("Phase").agg(
        Total_Units=("Unit", "count"),
        Vacant=("Is_Vacant", "sum"),
        Avg_Turn_Days=("Aging_Business_Days", "mean"),
        SLA_Breaches=("SLA_Breach", "sum"),
        Ready_Units=("Is_Unit_Ready", "sum"),
        Avg_Completion=("Task_Completion_Ratio", "mean"),
    ).round(1)

    phase_stats["Vacancy Rate"] = (
        phase_stats["Vacant"] / phase_stats["Total_Units"] * 100
    ).round(1)

    phase_stats["Compliance Rate"] = np.where(
        phase_stats["Vacant"] > 0,
        ((phase_stats["Vacant"] - phase_stats["SLA_Breaches"]) / phase_stats["Vacant"] * 100).round(1),
        100.0,
    )

    def indicator(avg):
        if pd.isna(avg):
            return ""
        if avg <= 6:
            return "Good"
        if avg <= 8:
            return "Watch"
        return "Critical"

    phase_stats["Performance"] = phase_stats["Avg_Turn_Days"].apply(indicator)

    phase_stats = phase_stats.sort_values("Avg_Turn_Days", na_position="last")
    phase_stats = phase_stats.reset_index()

    comparison = phase_stats[[
        "Phase", "Total_Units", "Vacant", "Avg_Turn_Days",
        "SLA_Breaches", "Ready_Units", "Avg_Completion",
        "Vacancy Rate", "Compliance Rate", "Performance",
    ]].copy()

    comparison = comparison.rename(columns={
        "Total_Units": "Units",
        "Avg_Turn_Days": "Avg Turn Days",
        "SLA_Breaches": "SLA Breaches",
        "Ready_Units": "Ready",
        "Avg_Completion": "Avg Completion %",
    })

    results = []

    results.append({
        "title": "Phase Performance Comparison",
        "table_name": "PhaseComparison",
        "df": comparison,
    })

    totals = pd.DataFrame({
        "Metric": [
            "Total Units",
            "Total Vacant",
            "Portfolio Avg Turn",
            "Total SLA Breaches",
            "Total Ready",
            "Portfolio Avg Completion",
            "Portfolio Compliance Rate",
        ],
        "Value": [
            total_units,
            int(comparison["Vacant"].sum()),
            f"{comparison['Avg Turn Days'].mean():.1f} days",
            int(comparison["SLA Breaches"].sum()),
            int(comparison["Ready"].sum()),
            f"{comparison['Avg Completion %'].mean():.1f}%",
            f"{comparison['Compliance Rate'].mean():.1f}%",
        ],
    })

    results.append({
        "title": "Portfolio Summary",
        "table_name": "PortfolioSummary",
        "df": totals,
    })

    best = comparison.head(2)
    worst = comparison.tail(2).iloc[::-1]

    perf_rows = []
    for _, r in best.iterrows():
        perf_rows.append({
            "Phase": r["Phase"],
            "Category": "Best Performer",
            "Avg Turn Days": r.get("Avg Turn Days", ""),
            "Compliance Rate": f"{r.get('Compliance Rate', '')}%",
        })
    for _, r in worst.iterrows():
        perf_rows.append({
            "Phase": r["Phase"],
            "Category": "Needs Attention",
            "Avg Turn Days": r.get("Avg Turn Days", ""),
            "Compliance Rate": f"{r.get('Compliance Rate', '')}%",
        })

    results.append({
        "title": "Best & Worst Performers",
        "table_name": "Performers",
        "df": pd.DataFrame(perf_rows),
    })

    return results

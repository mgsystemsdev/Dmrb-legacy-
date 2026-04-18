import pandas as pd
from datetime import date, timedelta
from pathlib import Path


def build_weekly_summary(
    df: pd.DataFrame,
    output_path: Path,
    total_portfolio: int = 0,
    today: date | None = None,
) -> Path:
    if today is None:
        today = date.today()

    week_start = today - timedelta(days=7)
    total_units = total_portfolio if total_portfolio > 0 else len(df)

    vacant = int(df["Is_Vacant"].sum())
    compliance = (
        (vacant - df["SLA_Breach"].sum()) / vacant * 100
        if vacant > 0
        else 100
    )
    ready = int(df["Is_Unit_Ready"].sum())

    sla_breaches = int(df["SLA_Breach"].sum())
    movein_risk_count = int(df["SLA_MoveIn_Breach"].sum())
    stalled = int(df["Is_Task_Stalled"].sum())
    plan_breaches = int(df["Plan_Breach"].sum())

    upcoming_movein = df[
        df["Is_MoveIn_Present"]
        & (df["Days_To_MoveIn"] >= 0)
        & (df["Days_To_MoveIn"] <= 14)
    ].sort_values("Days_To_MoveIn")

    upcoming_ready = df[
        df["Is_Ready_Declared"]
        & (~df["Is_Unit_Ready"])
    ].sort_values("Unit")

    vacant_status = df["Status"].fillna("").astype(str).str.strip().str.lower().str.startswith("vacant")
    wd_val = df["W_D"].fillna("").astype(str).str.strip().str.lower()
    no_wd = df[
        vacant_status & wd_val.isin(["", "no", "nan"])
    ].sort_values("Unit")

    movein_risk = df[df["SLA_MoveIn_Breach"] == True].sort_values("Days_To_MoveIn")

    aging_counts = df["Aging"].value_counts()
    aging_order = ["0\u201314", "15\u201330", "31\u201360", "61\u2013120", "120+"]

    email_body = f"""\
Subject: Weekly Property Operations Summary - {today.strftime('%B %d, %Y')}

{"=" * 62}
WEEKLY OPERATIONS SUMMARY
Week of {week_start.strftime('%B %d')} - {today.strftime('%B %d, %Y')}
{"=" * 62}

KEY METRICS

Total Portfolio:           {total_units:,}
Total Vacant Units:        {vacant}
SLA Compliance:            {compliance:.1f}%
Units Ready:               {ready}

{"=" * 62}

ALERTS

SLA Breaches:              {sla_breaches} units
Move-In Risk:              {movein_risk_count} units
Stalled Tasks:             {stalled} units
Plan Breaches:             {plan_breaches} units

{"=" * 62}

UPCOMING MOVE-INS ({len(upcoming_movein)} units)
"""

    for _, r in upcoming_movein.iterrows():
        dtm = r["Days_To_MoveIn"]
        days_str = f"{dtm:.0f}" if pd.notna(dtm) else "?"
        mi = pd.to_datetime(r["Move_in"], errors="coerce")
        mi_str = mi.strftime("%m/%d/%y") if pd.notna(mi) else "\u2014"
        email_body += f"\n  {r['Unit']:20} M-I: {mi_str}  ({days_str} days away)"

    email_body += f"\n\n{'=' * 62}\n"
    email_body += f"\nUPCOMING UNITS TO BE READY ({len(upcoming_ready)} units)\n"

    for _, r in upcoming_ready.iterrows():
        rd = pd.to_datetime(r["Ready_Date"], errors="coerce")
        rd_str = rd.strftime("%m/%d/%y") if pd.notna(rd) else "\u2014"
        email_body += f"\n  {r['Unit']:20} Ready Date: {rd_str}  Status: {r['Status']}"

    email_body += f"\n\n{'=' * 62}\n"
    email_body += f"\nUNITS WITH NO W/D ({len(no_wd)} units)\n"

    for _, r in no_wd.iterrows():
        email_body += f"\n  {r['Unit']:20} Status: {r['Status']}"

    email_body += f"\n\n{'=' * 62}\n"
    email_body += f"\nMOVE-IN RISK ({len(movein_risk)} units)\n"

    for _, r in movein_risk.iterrows():
        dtm = r["Days_To_MoveIn"]
        days_str = f"{dtm:.0f}" if pd.notna(dtm) else "?"
        task = r.get("Table_Current_Task", "")
        email_body += f"\n  {r['Unit']:20} {days_str} days to move-in  Task: {task}"

    email_body += f"\n\n{'=' * 62}\n"
    email_body += "\nAGING DISTRIBUTION\n"

    for bucket in aging_order:
        count = int(aging_counts.get(bucket, 0))
        email_body += f"\n{bucket:>10}  {count:>4} units"

    email_body += f"\n\n{'=' * 62}"
    email_body += "\n\nThis is an automated report generated from DMRB Pipeline.\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(email_body)

    return output_path

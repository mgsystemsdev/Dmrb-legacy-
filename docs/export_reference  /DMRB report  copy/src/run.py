import pandas as pd
from pathlib import Path

from facts import run_facts
from intelligence import run_intelligence
from sla import run_sla
from views.dashboard import build_dashboard_table1, build_dashboard_table2, build_aging_tables, build_active_aging_tables
from views.operations import (
    build_move_in_dashboard,
    build_sla_breach,
    build_inspection_sla_breach,
    build_plan_breach,
)
from views.task_views import build_task_stalled, build_clean_turn, build_task_flow
from views.schedule import build_schedule_tables
from views.upcoming import build_upcoming_tables
from views.wd_audit import build_wd_audit

from views.walk_board import build_walk_board
from reports.daily_ops import build_daily_ops_report
from reports.priority import build_priority_report
from reports.phase_performance import build_phase_performance
from reports.visual_dashboard import build_visual_dashboard
from reports.weekly_summary import build_weekly_summary
from io_excel import read_excel_table, write_excel_file


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

RAW_EXCEL_PATH = BASE_DIR / "raw" / "DMRB_raw.xlsx"
OUTPUT_EXCEL_PATH = BASE_DIR / "output" / "DMRB_REPORTS.xlsx"
OUTPUT_CHART_PATH = BASE_DIR / "output" / "Dashboard_Chart.png"
OUTPUT_WEEKLY_PATH = BASE_DIR / "output" / "Weekly_Summary.txt"

SHEET_NAME = "DMRB "
TABLE_NAME = "DMRB5"

TOTAL_PORTFOLIO_UNITS = 1244


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    print("▶ Reading raw Excel table...")
    df_raw = read_excel_table(
        path=RAW_EXCEL_PATH,
        sheet_name=SHEET_NAME,
        table_name=TABLE_NAME
    )

    print("▶ Running Stage 1: Core Facts")
    df_facts = run_facts(df_raw)

    print("▶ Running Stage 2: Operational Intelligence")
    df_intel = run_intelligence(df_facts)

    print("▶ Running Stage 3: SLA & Risk Enforcement")
    df_sla = run_sla(df_intel)

    print("▶ Saving ML history snapshot...")
    snapshot = df_sla.copy()
    snapshot["snapshot_date"] = pd.Timestamp.today().normalize()
    history_path = BASE_DIR / "history" / "snapshots.csv"
    history_path.parent.mkdir(exist_ok=True)
    snapshot.to_csv(
        history_path,
        mode="a",
        header=not history_path.exists(),
        index=False,
    )
    print(f"📸 Snapshot appended to: {history_path}")

    print("▶ Building Dashboard...")
    df_table1 = build_dashboard_table1(df_sla)
    df_table2 = build_dashboard_table2(df_sla)

    print("▶ Building Aging tables...")
    aging_raw = build_aging_tables(df_sla)

    aging_entries = []
    current_row = 5
    for item in aging_raw:
        aging_entries.append({
            "df": item["df"],
            "start_col": 2,
            "start_row": current_row,
            "table_name": item["table_name"],
            "title": item["title"],
        })
        current_row += len(item["df"]) + 1 + 4

    print("▶ Building Active Aging tables...")
    active_aging_raw = build_active_aging_tables(df_sla)

    active_aging_entries = []
    current_row = 5
    for item in active_aging_raw:
        active_aging_entries.append({
            "df": item["df"],
            "start_col": 2,
            "start_row": current_row,
            "table_name": item["table_name"],
            "title": item["title"],
        })
        current_row += len(item["df"]) + 1 + 4

    print("▶ Building Operations views...")
    df_move_in = build_move_in_dashboard(df_sla)
    df_sla_breach = build_sla_breach(df_sla)
    df_insp_breach = build_inspection_sla_breach(df_sla)
    df_plan_breach = build_plan_breach(df_sla)

    ops_tables = [
        ("Move In Dashboard", "OpsMoveIn", df_move_in),
        ("SLA Breach (Turn Overdue Over 10 Days)", "OpsSLABreach", df_sla_breach),
        ("Inspection SLA Breach", "OpsInspBreach", df_insp_breach),
        ("Plan Breach", "OpsPlanBreach", df_plan_breach),
    ]

    ops_entries = []
    current_row = 5
    for title, table_name, df_op in ops_tables:
        ops_entries.append({
            "df": df_op,
            "start_col": 2,
            "start_row": current_row,
            "table_name": table_name,
            "title": title,
        })
        current_row += len(df_op) + 1 + 4

    print("▶ Building Task views...")
    df_stalled = build_task_stalled(df_sla)
    df_clean = build_clean_turn(df_sla)
    df_flow = build_task_flow(df_sla)

    task_tables = [
        ("Task Stalled", "TaskStalled", df_stalled),
        ("Clean Turn", "CleanTurn", df_clean),
        ("Task Flow", "TaskFlow", df_flow),
    ]

    task_entries = []
    current_row = 5
    for title, table_name, df_t in task_tables:
        task_entries.append({
            "df": df_t,
            "start_col": 2,
            "start_row": current_row,
            "table_name": table_name,
            "title": title,
        })
        current_row += len(df_t) + 1 + 4

    print("▶ Building Schedule views...")
    sched_raw = build_schedule_tables(df_sla)

    sched_entries = []
    current_row = 5
    for item in sched_raw:
        sched_entries.append({
            "df": item["df"],
            "start_col": 2,
            "start_row": current_row,
            "table_name": item["table_name"],
            "title": item["title"],
        })
        current_row += len(item["df"]) + 1 + 4

    print("▶ Building Upcoming views...")
    upcoming_raw = build_upcoming_tables(df_sla)

    upcoming_entries = []
    current_row = 5
    for item in upcoming_raw:
        upcoming_entries.append({
            "df": item["df"],
            "start_col": 2,
            "start_row": current_row,
            "table_name": item["table_name"],
            "title": item["title"],
        })
        current_row += len(item["df"]) + 1 + 4

    print("▶ Building W/D Audit & Walking Path Board...")
    df_wd = build_wd_audit(df_sla)
    df_walk = build_walk_board(df_sla)

    print("▶ Building Daily Ops Report...")
    daily_raw = build_daily_ops_report(df_sla, total_portfolio=TOTAL_PORTFOLIO_UNITS)

    daily_entries = []
    current_row = 5
    for item in daily_raw:
        daily_entries.append({
            "df": item["df"],
            "start_col": 2,
            "start_row": current_row,
            "table_name": item["table_name"],
            "title": item["title"],
        })
        current_row += len(item["df"]) + 1 + 4

    print("▶ Building Priority Report...")
    priority_raw = build_priority_report(df_sla)

    priority_entries = []
    current_row = 5
    for item in priority_raw:
        priority_entries.append({
            "df": item["df"],
            "start_col": 2,
            "start_row": current_row,
            "table_name": item["table_name"],
            "title": item["title"],
        })
        current_row += len(item["df"]) + 1 + 4

    print("▶ Building Phase Performance Report...")
    phase_raw = build_phase_performance(df_sla, total_portfolio=TOTAL_PORTFOLIO_UNITS)

    phase_entries = []
    current_row = 5
    for item in phase_raw:
        phase_entries.append({
            "df": item["df"],
            "start_col": 2,
            "start_row": current_row,
            "table_name": item["table_name"],
            "title": item["title"],
        })
        current_row += len(item["df"]) + 1 + 4

    DATE_COLS = ["Move_out", "Ready_Date", "Move_in", "Insp", "Paint", "MR", "HK", "CC"]
    df_report = df_sla.copy()
    for col in DATE_COLS:
        if col in df_report.columns:
            df_report[col] = pd.to_datetime(df_report[col], errors="coerce")

    print("▶ Generating Visual Dashboard...")
    chart_path = build_visual_dashboard(
        df_sla,
        output_path=OUTPUT_CHART_PATH,
        total_portfolio=TOTAL_PORTFOLIO_UNITS,
    )
    print(f"📊 Chart saved to: {chart_path}")

    print("▶ Generating Weekly Summary...")
    weekly_path = build_weekly_summary(
        df_sla,
        output_path=OUTPUT_WEEKLY_PATH,
        total_portfolio=TOTAL_PORTFOLIO_UNITS,
    )
    print(f"📧 Weekly summary saved to: {weekly_path}")

    print("▶ Writing output Excel file...")
    write_excel_file(
        path=OUTPUT_EXCEL_PATH,
        sheets={
            "Dashboard": [
                {
                    "df": df_table1,
                    "start_col": 2,
                    "start_row": 5,
                    "table_name": "DashboardVacant",
                    "title": "Units Overview",
                },
            ],
            "Aging": aging_entries,
            "Active Aging": active_aging_entries,
            "Operations": ops_entries,
            "Walking Path Board": [
                {
                    "df": df_walk,
                    "start_col": 2,
                    "start_row": 5,
                    "table_name": "WalkBoard",
                    "title": "Walking Path Board",
                },
            ],
            "Tasks": task_entries,
            "Schedule": sched_entries,
            "Upcoming": upcoming_entries,
            "WD Audit": [
                {
                    "df": df_wd,
                    "start_col": 2,
                    "start_row": 5,
                    "table_name": "WDAudit",
                    "title": "W/D Audit",
                },
            ],
            "Daily Ops": daily_entries,
            "Priority": priority_entries,
            "Phase Performance": phase_entries,
            "DMRB_REPORTS": df_report,
        },
    )

    print("✅ Pipeline complete.")
    print(f"📄 Output written to: {OUTPUT_EXCEL_PATH}")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

import pandas as pd
import numpy as np

TASK_SEQUENCE = ["Inspection", "Paint", "MR", "HK", "CC"]
TASK_DATE_COL = {
    "Inspection": "Insp",
    "Paint": "Paint",
    "MR": "MR",
    "HK": "HK",
    "CC": "CC",
}


def build_task_stalled(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df["Is_Task_Stalled"] == True].copy()

    df["Task_Completion_Ratio"] = pd.to_numeric(df["Task_Completion_Ratio"], errors="coerce")
    df = df.sort_values("Task_Completion_Ratio", ascending=True, na_position="last").reset_index(drop=True)

    view = df[[
        "P", "Unit", "Table_Current_Task", "Task_Completion_Ratio",
        "Operational_State", "Attention_Badge",
    ]].copy()

    view = view.rename(columns={
        "P": "Phase",
        "Table_Current_Task": "Current Task",
        "Task_Completion_Ratio": "Progress %",
        "Operational_State": "Execution State",
        "Attention_Badge": "⚠️ Alert",
    })

    view["Phase"] = pd.to_numeric(view["Phase"], errors="coerce")

    return view


def build_clean_turn(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[
        (df["Task_State"] == "All Tasks Complete") &
        (df["Is_Vacant"] == True)
    ].copy()

    df = df.sort_values("Unit", ascending=True).reset_index(drop=True)

    view = df[[
        "P", "Unit", "Status", "Operational_State", "Task_Completion_Ratio",
    ]].copy()

    view = view.rename(columns={
        "P": "Phase",
        "Operational_State": "Execution State",
        "Task_Completion_Ratio": "Progress %",
    })

    view["Phase"] = pd.to_numeric(view["Phase"], errors="coerce")

    return view


def _lookup_task_date(row, task_col_name):
    task = row.get(task_col_name, "")
    if not task or task == "":
        return None
    date_col = TASK_DATE_COL.get(task)
    if date_col is None:
        return None
    val = row.get(date_col)
    if pd.isna(val) or val == "":
        return None
    return val


def build_task_flow(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[
        (df["In_Turn_Execution"] == True) &
        (df["Task_State"] == "In Progress")
    ].copy()

    for col in TASK_DATE_COL.values():
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    df["Task Date"] = df.apply(lambda r: _lookup_task_date(r, "Table_Current_Task"), axis=1)
    df["Next Date"] = df.apply(lambda r: _lookup_task_date(r, "Table_Next_Task"), axis=1)

    df["Task Date"] = pd.to_datetime(df["Task Date"], errors="coerce")
    df["Next Date"] = pd.to_datetime(df["Next Date"], errors="coerce")

    df = df.sort_values("Task_Completion_Ratio", ascending=True, na_position="last").reset_index(drop=True)

    view = df[[
        "P", "Unit", "Table_Current_Task", "Task Date",
        "Table_Next_Task", "Next Date", "Task_Completion_Ratio",
    ]].copy()

    view = view.rename(columns={
        "P": "Phase",
        "Table_Current_Task": "Task",
        "Table_Next_Task": "Next",
        "Task_Completion_Ratio": "Progress %",
    })

    view["Phase"] = pd.to_numeric(view["Phase"], errors="coerce")

    return view

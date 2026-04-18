import pandas as pd


def _prep_dates(df, cols):
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def build_move_in_dashboard(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df["Is_MoveIn_Present"] & ~df["Is_Unit_Ready_For_Moving"]].copy()
    df = _prep_dates(df, ["Move_out", "Move_in"])
    df["DV"] = pd.to_numeric(df["DV"], errors="coerce")

    df = df.sort_values("Move_in", ascending=True, na_position="last").reset_index(drop=True)

    view = df[[
        "P", "Unit", "Status", "Move_out", "DV", "Move_in", "DTBR", "N/V/M",
        "Task_Completion_Ratio", "Table_Current_Task",
        "Operational_State", "Attention_Badge",
    ]].copy()

    view = view.rename(columns={
        "P": "Phase",
        "Move_out": "M-O",
        "DV": "DV",
        "Move_in": "M-I",
        "Task_Completion_Ratio": "Progress %",
        "Table_Current_Task": "Current Task",
        "Operational_State": "Execution Reason",
        "Attention_Badge": "⚠️ Alert",
    })

    view["Phase"] = pd.to_numeric(view["Phase"], errors="coerce")

    return view


def build_sla_breach(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df["SLA_Breach"] == True].copy()
    df = _prep_dates(df, ["Move_out"])
    df["DV"] = pd.to_numeric(df["DV"], errors="coerce")

    df = df.sort_values("Aging_Business_Days", ascending=False, na_position="last").reset_index(drop=True)

    view = df[[
        "P", "Unit", "Status", "Move_out", "DV", "N/V/M",
        "Table_Current_Task", "Task_Completion_Ratio",
        "Attention_Badge", "Note_Category",
    ]].copy()

    view = view.rename(columns={
        "P": "Phase",
        "Move_out": "M-O",
        "Table_Current_Task": "Current Task",
        "Task_Completion_Ratio": "Progress %",
        "Attention_Badge": "⚠️ Alert",
        "Note_Category": "Notes Category",
    })

    view["Phase"] = pd.to_numeric(view["Phase"], errors="coerce")

    return view


def build_inspection_sla_breach(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df["Inspection_SLA_Breach"] == True].copy()
    df = _prep_dates(df, ["Move_out", "Insp"])

    df = df.sort_values("Aging_Business_Days", ascending=False, na_position="last").reset_index(drop=True)

    view = df[[
        "P", "Unit", "Status", "Move_out", "Insp", "Insp_status",
        "Attention_Badge",
    ]].copy()

    view = view.rename(columns={
        "P": "Phase",
        "Move_out": "M-O",
        "Insp": "Insp Date",
        "Insp_status": "Inspection",
        "Attention_Badge": "⚠️ Alert",
    })

    view["Phase"] = pd.to_numeric(view["Phase"], errors="coerce")

    return view


def build_plan_breach(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df["Plan_Breach"] == True].copy()
    df = _prep_dates(df, ["Ready_Date"])

    df = df.sort_values("Aging_Business_Days", ascending=False, na_position="last").reset_index(drop=True)

    view = df[[
        "P", "Unit", "Ready_Date", "Status",
        "Operational_State", "Table_Current_Task", "Attention_Badge",
    ]].copy()

    view = view.rename(columns={
        "P": "Phase",
        "Ready_Date": "Ready Date",
        "Operational_State": "Execution State",
        "Table_Current_Task": "Execution Reason",
        "Attention_Badge": "⚠️ Alert",
    })

    view["Phase"] = pd.to_numeric(view["Phase"], errors="coerce")

    return view

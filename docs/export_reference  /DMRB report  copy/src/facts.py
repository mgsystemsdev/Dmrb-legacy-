import pandas as pd
import numpy as np
from datetime import date

# ============================================================
# CONFIGURATION
# ============================================================

EXCEL_COLUMNS = [
    "Unit","Status","Move_out","Ready_Date","DV","Move_in","DTBR","N/V/M",
    "Insp","Insp_status","Paint","Paint_status","MR","MR_Status",
    "HK","HK_Status","CC","CC_status","Assign","W_D","QC","P","B","U","Notes"
]

TASK_SEQUENCE = ["Inspection", "Paint", "MR", "HK", "CC"]

# task → (date_col, status_col, due_day_offset)
TASK_COLS = {
    "Inspection": ("Insp", "Insp_status", 1),
    "Paint": ("Paint", "Paint_status", 2),
    "MR": ("MR", "MR_Status", 3),
    "HK": ("HK", "HK_Status", 6),
    "CC": ("CC", "CC_status", 7),
}

ALLOWED_PHASES = ["5", "7", "8"]

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def has_value(v):
    return pd.notna(v) and str(v).strip() != ""


def norm_text(v):
    return "" if pd.isna(v) else str(v).strip()


def norm_status(v):
    if pd.isna(v) or str(v).strip() == "":
        return "Not Started"
    return str(v).strip().title()


def is_done(v):
    return str(v).strip().upper() == "DONE"


def business_days(start, end):
    """
    Defensive business-day calculation.
    Returns NaN if dates are missing or invalid.
    """
    try:
        if pd.isna(start) or pd.isna(end):
            return np.nan

        s = pd.to_datetime(start, errors="coerce")
        e = pd.to_datetime(end, errors="coerce")

        if pd.isna(s) or pd.isna(e):
            return np.nan

        return np.busday_count(s.date(), e.date())
    except Exception:
        return np.nan


# ============================================================
# STAGE 1 — CORE FACTS
# ============================================================

def run_facts(df: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    if today is None:
        today = date.today()

    df = df.copy()

    # --------------------------------------------------------
    # Normalize date columns
    # --------------------------------------------------------
    df["Move_in"] = pd.to_datetime(df["Move_in"], errors="coerce")
    df["Ready_Date"] = pd.to_datetime(df["Ready_Date"], errors="coerce")
    df["Move_out"] = pd.to_datetime(df["Move_out"], errors="coerce")

    # --------------------------------------------------------
    # Convert NaT dates to empty strings for Excel compatibility
    # --------------------------------------------------------
    date_columns = [
        "Move_out", "Ready_Date", "Move_in",
        "Insp", "Paint", "MR", "HK", "CC"
    ]

    for col in date_columns:
        if col in df.columns:
            df[col] = df[col].astype(object).where(df[col].notna(), "")

    # --------------------------------------------------------
    # Notes context
    # --------------------------------------------------------
    df["Note_Text"] = df["Notes"].apply(norm_text)
    df["Has_Note_Context"] = df["Note_Text"].apply(has_value)

    def note_category(txt: str) -> str:
        t = txt.upper()
        if "HOLD" in t:
            return "HOLD"
        if "ISSUE" in t:
            return "ISSUE"
        if "REOPEN" in t:
            return "REOPEN"
        if "DECISION" in t:
            return "DECISION"
        if "MAYBE" in t:
            return "MAYBE"
        return ""

    df["Note_Category"] = df["Note_Text"].apply(note_category)

    # --------------------------------------------------------
    # Assignment & presence flags
    # --------------------------------------------------------
    df["Has_Assignment"] = df["Assign"].apply(
        lambda x: has_value(x) and str(x).strip().lower() != "total"
    )

    df["Is_MoveIn_Present"] = df["Move_in"].ne("")
    df["Is_Ready_Declared"] = df["Ready_Date"].ne("")

    # --------------------------------------------------------
    # Status flags from N/V/M
    # --------------------------------------------------------
    nvm = df["N/V/M"].astype(str).str.strip().str.upper()

    df["Is_Vacant"] = nvm.eq("VACANT")
    df["Is_SMI"] = nvm.str.contains("SMI|MOVE IN", na=False)
    df["Is_On_Notice"] = nvm.str.contains("NOTICE", na=False)

    # --------------------------------------------------------
    # Phase & QC flags
    # --------------------------------------------------------
    df["Is_Allowed_Phase"] = (
        df["P"].fillna("").astype(str).str.strip().isin(ALLOWED_PHASES)
    )

    df["Is_QC_Done"] = (
        df["QC"].astype(str).str.strip().str.upper().eq("DONE")
    )

    # --------------------------------------------------------
    # Aging (business days since move-out)
    # --------------------------------------------------------
    df["Aging_Business_Days"] = df["Move_out"].apply(
        lambda d: business_days(d, today)
    )

    AGING_BINS = [0, 10, 20, 30, 60, 120, float("inf")]
    AGING_LABELS = ["1–10", "11–20", "21–30", "31–60", "61–120", "120+"]
    dv_numeric = pd.to_numeric(df["DV"], errors="coerce")
    df["Aging"] = pd.cut(
        dv_numeric,
        bins=AGING_BINS,
        labels=AGING_LABELS,
        right=True,
    ).astype(object).fillna("")

    # --------------------------------------------------------
    # Task mechanics
    # --------------------------------------------------------
    status_cols = [TASK_COLS[t][1] for t in TASK_SEQUENCE]

    for col in status_cols:
        df[col] = df[col].apply(norm_status)

    # Task state
    all_done = df[status_cols].eq("Done").all(axis=1)
    none_started = df[status_cols].eq("Not Started").all(axis=1)

    df["Task_State"] = np.select(
        [all_done, none_started],
        ["All Tasks Complete", "Not Started"],
        default="In Progress"
    )

    # Task completion ratio
    df["Task_Completion_Ratio"] = (
        df[status_cols].eq("Done").sum(axis=1) / len(status_cols) * 100
    )

    # Current / next task
    done_matrix = df[status_cols].eq("Done")
    first_not_done = (~done_matrix).idxmax(axis=1)
    cur_index = first_not_done.map(
        lambda name: status_cols.index(name) if name in status_cols else np.nan
    )

    df["Table_Current_Task"] = cur_index.map(
        lambda i: TASK_SEQUENCE[int(i)] if pd.notna(i) else ""
    )

    df["Table_Next_Task"] = cur_index.add(1).map(
        lambda i: TASK_SEQUENCE[int(i)]
        if pd.notna(i) and i < len(TASK_SEQUENCE)
        else ""
    )

    # Stall detection
    stall_matrix = pd.DataFrame({
        task: (
            df["Is_Vacant"] &
            ~df[TASK_COLS[task][1]].eq("Done") &
            (df["Aging_Business_Days"] > (TASK_COLS[task][2] + 1))
        )
        for task in TASK_SEQUENCE
    })

    df["Is_Task_Stalled"] = stall_matrix.any(axis=1)

    return df

import pandas as pd

TASK_DEFS = [
    {
        "title": "Inspections",
        "table_name": "UpInspections",
        "task_name": "Inspection",
        "date_col": "Insp",
        "status_col": "Insp_status",
        "date_label": "Inspection Date",
        "status_label": "Inspection Status",
        "extra_cols": [],
    },
    {
        "title": "Paint",
        "table_name": "UpPaint",
        "task_name": "Paint",
        "date_col": "Paint",
        "status_col": "Paint_status",
        "date_label": "Paint Date",
        "status_label": "Paint Status",
        "extra_cols": [],
    },
    {
        "title": "Make Ready",
        "table_name": "UpMR",
        "task_name": "MR",
        "date_col": "MR",
        "status_col": "MR_Status",
        "date_label": "MR Date",
        "status_label": "MR Status",
        "extra_cols": [("Assign", "Assigned To")],
    },
    {
        "title": "House Keeping",
        "table_name": "UpHK",
        "task_name": "HK",
        "date_col": "HK",
        "status_col": "HK_Status",
        "date_label": "HK Date",
        "status_label": "HK Status",
        "extra_cols": [],
    },
    {
        "title": "Carpet Clean",
        "table_name": "UpCC",
        "task_name": "CC",
        "date_col": "CC",
        "status_col": "CC_status",
        "date_label": "CC Date",
        "status_label": "CC Status",
        "extra_cols": [],
    },
]

TASK_SEQUENCE = ["Inspection", "Paint", "MR", "HK", "CC"]

ALLOWED_PHASES = {"7", "8"}


def _next_business_day(from_date: pd.Timestamp) -> pd.Timestamp:
    nbd = from_date + pd.Timedelta(days=1)
    while nbd.weekday() >= 5:
        nbd += pd.Timedelta(days=1)
    return nbd


def _assign_upcoming_dates(row, today):
    """Walk the task sequence for a single unit and assign staggered dates.

    Each scheduled task gets at least the next business day after the
    previous scheduled task, so no two tasks land on the same day.
    """
    cursor = _next_business_day(today)
    dates = {}

    for task_name in TASK_SEQUENCE:
        td = next(t for t in TASK_DEFS if t["task_name"] == task_name)
        date_col = td["date_col"]
        status_col = td["status_col"]

        status = str(row.get(status_col, "")).strip().lower()
        if status == "done":
            continue

        if status != "scheduled":
            continue

        orig = row.get(date_col)
        orig = pd.to_datetime(orig, errors="coerce")
        if pd.isna(orig):
            continue

        effective = max(orig, cursor) if orig > today else cursor
        dates[task_name] = effective
        cursor = _next_business_day(effective)

    return dates


def _spread_mr_dates(wdf, all_dates):
    """Ensure no assignee has two MR units on the same day."""
    assignee_cursors = {}

    rows = []
    for idx in wdf.index:
        if "MR" in all_dates.at[idx]:
            assignee = str(wdf.at[idx, "Assign"]).strip()
            rows.append((idx, assignee, all_dates.at[idx]["MR"]))

    rows.sort(key=lambda x: x[2])

    for idx, assignee, mr_date in rows:
        cursor = assignee_cursors.get(assignee)
        if cursor is not None and mr_date < cursor:
            mr_date = cursor

        unit_dates = dict(all_dates.at[idx])
        unit_dates["MR"] = mr_date
        all_dates.at[idx] = unit_dates
        assignee_cursors[assignee] = _next_business_day(mr_date)

    return all_dates


def build_upcoming_tables(df: pd.DataFrame) -> list[dict]:
    today = pd.Timestamp.today().normalize()

    phase_mask = df["P"].fillna("").astype(str).str.strip().isin(ALLOWED_PHASES)
    wdf = df[phase_mask].copy()

    for td in TASK_DEFS:
        wdf[td["date_col"]] = pd.to_datetime(wdf[td["date_col"]], errors="coerce")

    all_dates = wdf.apply(lambda r: _assign_upcoming_dates(r, today), axis=1)

    all_dates = _spread_mr_dates(wdf, all_dates)

    results = []

    for task_def in TASK_DEFS:
        task_name = task_def["task_name"]
        date_col = task_def["date_col"]
        status_col = task_def["status_col"]
        effective_col = f"Effective_{date_col}"

        wdf[effective_col] = all_dates.apply(lambda d: d.get(task_name))
        tdf = wdf[wdf[effective_col].notna()].copy()

        tdf = tdf.sort_values(effective_col, ascending=True, na_position="last").reset_index(drop=True)

        select_cols = ["P", "Unit", effective_col, status_col]
        rename_map = {
            "P": "Phase",
            effective_col: task_def["date_label"],
            status_col: task_def["status_label"],
        }

        for src, dst in task_def["extra_cols"]:
            select_cols.append(src)
            rename_map[src] = dst

        view = tdf[select_cols].copy()
        view = view.rename(columns=rename_map)
        view["Phase"] = pd.to_numeric(view["Phase"], errors="coerce")

        results.append({
            "title": task_def["title"],
            "table_name": task_def["table_name"],
            "df": view,
        })

    return results

import pandas as pd

TASK_DEFS = [
    {
        "title": "Inspections",
        "table_name": "SchedInspections",
        "date_col": "Insp",
        "status_col": "Insp_status",
        "date_label": "Inspection Date",
        "status_label": "Inspection Status",
        "extra_cols": [],
    },
    {
        "title": "Paint",
        "table_name": "SchedPaint",
        "date_col": "Paint",
        "status_col": "Paint_status",
        "date_label": "Paint Date",
        "status_label": "Paint Status",
        "extra_cols": [],
    },
    {
        "title": "Make Ready",
        "table_name": "SchedMR",
        "date_col": "MR",
        "status_col": "MR_Status",
        "date_label": "MR Date",
        "status_label": "MR Status",
        "extra_cols": [("Assign", "Assigned To")],
    },
    {
        "title": "House Keeping",
        "table_name": "SchedHK",
        "date_col": "HK",
        "status_col": "HK_Status",
        "date_label": "HK Date",
        "status_label": "HK Status",
        "extra_cols": [],
    },
    {
        "title": "Carpet Clean",
        "table_name": "SchedCC",
        "date_col": "CC",
        "status_col": "CC_status",
        "date_label": "CC Date",
        "status_label": "CC Status",
        "extra_cols": [],
    },
]


def build_schedule_tables(df: pd.DataFrame) -> list[dict]:
    results = []

    for task_def in TASK_DEFS:
        tdf = df.copy()
        date_col = task_def["date_col"]
        status_col = task_def["status_col"]

        tdf[date_col] = pd.to_datetime(tdf[date_col], errors="coerce")

        status_norm = tdf[status_col].fillna("").astype(str).str.strip().str.lower()
        tdf = tdf[
            tdf[date_col].notna() &
            status_norm.isin({"in progress", "scheduled"})
        ].copy()
        tdf = tdf.sort_values(date_col, ascending=True, na_position="last").reset_index(drop=True)

        select_cols = ["P", "Unit", date_col, status_col]
        rename_map = {
            "P": "Phase",
            date_col: task_def["date_label"],
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

import pandas as pd

TABLE1_REQUIRED = [
    "Unit",
    "Status",
    "DV",
    "Move_in",
    "Attention_Badge",
    "Is_Vacant",
    "Is_Allowed_Phase",
]

TABLE2_REQUIRED = [
    "Unit",
    "Status",
    "Aging",
    "DV",
    "Is_Vacant",
    "Is_Allowed_Phase",
    "P",
]

AGING_ORDER = ["1–10", "11–20", "21–30", "31–60", "61–120", "120+"]


def build_dashboard_table1(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    missing = [c for c in TABLE1_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["Move_in"] = pd.to_datetime(df["Move_in"], errors="coerce")
    df["DV"] = pd.to_numeric(df["DV"], errors="coerce")

    df = df.sort_values(
        by=["Move_in", "DV"],
        ascending=[True, False],
        na_position="last",
    ).reset_index(drop=True)

    df_view = df[["P", "Unit", "Status", "DV", "Move_in", "Attention_Badge"]].copy()

    df_view = df_view.rename(columns={
        "P": "Phase",
        "DV": "Days Vacant",
        "Move_in": "M-I Date",
        "Attention_Badge": "⚠️ Alert",
    })

    df_view["Phase"] = pd.to_numeric(df_view["Phase"], errors="coerce")
    df_view["M-I Date"] = pd.to_datetime(df_view["M-I Date"], errors="coerce")

    return df_view


def _build_aging_buckets(df: pd.DataFrame) -> pd.DataFrame:
    df["DV"] = pd.to_numeric(df["DV"], errors="coerce")

    columns = {}
    max_len = 0

    for bucket in AGING_ORDER:
        bucket_df = df[df["Aging"] == bucket].copy()
        bucket_df = bucket_df.sort_values("DV", ascending=False)

        units = bucket_df.apply(
            lambda r: f"{r['Unit']} ({r['Status']}) | DV-{int(r['DV']) if pd.notna(r['DV']) else '?'}",
            axis=1,
        ).tolist()

        columns[bucket] = units
        max_len = max(max_len, len(units))

    for k in columns:
        columns[k] += [""] * (max_len - len(columns[k]))

    return pd.DataFrame(columns)


def build_dashboard_table2(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    missing = [c for c in TABLE2_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    return _build_aging_buckets(df)


def build_aging_tables(df: pd.DataFrame) -> list[dict]:
    df = df.copy()

    missing = [c for c in TABLE2_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    status_norm = df["Status"].astype(str).str.strip().str.upper()

    overall = _build_aging_buckets(df)
    vacant_ready = _build_aging_buckets(df[status_norm == "VACANT READY"])
    vacant_not_ready = _build_aging_buckets(df[status_norm == "VACANT NOT READY"])

    return [
        {"df": overall, "table_name": "AgingAll", "title": "Aging Buckets — All Units"},
        {"df": vacant_ready, "table_name": "AgingReady", "title": "Aging Buckets — Vacant Ready"},
        {"df": vacant_not_ready, "table_name": "AgingNotReady", "title": "Aging Buckets — Vacant Not Ready"},
    ]


SHORT_AGING_ORDER = ["1–10", "11–20"]


def _build_short_aging_buckets(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["DV"] = pd.to_numeric(df["DV"], errors="coerce")

    columns = {}
    max_len = 0

    for bucket in SHORT_AGING_ORDER:
        bucket_df = df[df["Aging"] == bucket].copy()
        bucket_df = bucket_df.sort_values("DV", ascending=False)

        units = bucket_df.apply(
            lambda r: f"{r['Unit']} ({r['Status']}) | DV-{int(r['DV']) if pd.notna(r['DV']) else '?'}",
            axis=1,
        ).tolist()

        columns[bucket] = units
        max_len = max(max_len, len(units))

    for k in columns:
        columns[k] += [""] * (max_len - len(columns[k]))

    return pd.DataFrame(columns) if max_len > 0 else pd.DataFrame(columns={b: [] for b in SHORT_AGING_ORDER})


def build_active_aging_tables(df: pd.DataFrame) -> list[dict]:
    """
    Short aging (first 2 buckets only), Vacant Not Ready only,
    one table per phase (5, 7, 8).
    """
    df = df.copy()

    missing = [c for c in TABLE2_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    status_norm = df["Status"].astype(str).str.strip().str.upper()
    vnr = df[status_norm == "VACANT NOT READY"]

    tables = []
    for phase in ["5", "7", "8"]:
        phase_df = vnr[vnr["P"].astype(str).str.strip() == phase]
        bucket_df = _build_short_aging_buckets(phase_df)
        tables.append({
            "df": bucket_df,
            "table_name": f"ActiveAgingP{phase}",
            "title": f"Active Aging — Phase {phase} (Vacant Not Ready)",
        })

    return tables

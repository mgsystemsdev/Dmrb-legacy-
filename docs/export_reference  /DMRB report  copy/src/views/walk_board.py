import pandas as pd


def build_walk_board(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df["Status"].fillna("").astype(str).str.strip().str.lower().str.startswith("vacant")].copy()
    df = df.sort_values("Unit", ascending=True).reset_index(drop=True)

    view = df[[
        "P", "B", "Unit", "Status", "Attention_Badge",
        "Insp_status", "Paint_status", "MR_Status",
        "HK_Status", "CC_status", "QC",
    ]].copy()

    view = view.rename(columns={
        "P": "Phase",
        "B": "Building",
        "Attention_Badge": "Move Ins ⚠️ Alert",
        "Insp_status": "Inspection",
        "Paint_status": "Paint",
        "MR_Status": "MR",
        "HK_Status": "HK",
        "CC_status": "CC",
    })

    view["Phase"] = pd.to_numeric(view["Phase"], errors="coerce")
    view["Building"] = pd.to_numeric(view["Building"], errors="coerce")
    view["Notes"] = ""

    return view

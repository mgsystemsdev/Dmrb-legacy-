import pandas as pd


def build_wd_audit(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df["Status"].fillna("").astype(str).str.strip().str.lower().str.startswith("vacant")].copy()
    df = df.sort_values("Unit", ascending=True).reset_index(drop=True)

    view = df[["P", "Unit", "W_D"]].copy()
    view = view.rename(columns={"P": "Phase", "W_D": "W/D"})
    view["Phase"] = pd.to_numeric(view["Phase"], errors="coerce")
    view["W/D"] = view["W/D"].fillna("").astype(str).str.strip()

    return view

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import streamlit as st
import pandas as pd

from facts import run_facts
from intelligence import run_intelligence
from sla import run_sla

# -------------------------------------------------
# App configuration
# -------------------------------------------------
st.set_page_config(
    page_title="Turnover Operations",
    layout="wide",
)

# -------------------------------------------------
# Central data load (single source of truth)
# -------------------------------------------------
@st.cache_data
def load_data():
    df = pd.read_excel("raw/DMRB_raw.xlsx", sheet_name="DMRB ")

    # Column hygiene
    df = df.loc[:, df.columns.notna()]
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    df = df.loc[:, ~df.columns.astype(str).str.match(r"^nan", case=False)]
    df.columns = [str(c).strip() for c in df.columns]

    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].map(
            lambda v: v.decode("utf-8", "replace") if isinstance(v, (bytes, bytearray)) else v
        )
        types = set(type(v) for v in df[col].dropna())
        if len(types) > 1:
            df[col] = df[col].astype(str).replace("nan", None)

    return df


@st.cache_data
def enrich(df):
    df = run_facts(df)
    df = run_intelligence(df)
    df = run_sla(df)
    return df


df_prepared = enrich(load_data())

# -------------------------------------------------
# Page registry (scalable routing)
# -------------------------------------------------
PAGES = {
    "🚩 Flag Bridge": "ui.viewsst.flag_bridge_view",
    "🤖 Ops Assistant": "ui.viewsst.ai_chat",
    "📋 Unit Overview": "ui.viewsst.unit_overview",
    "🪪 Unit Cards": "ui.viewsst.unit_cards",
    "🎯 Ops Command": "ui.viewsst.ops_command",
    "📊 Pivot Analytics": "ui.viewsst.pivot_analytics",
    "🔮 Predict": "ui.viewsst.predict",
    "📄 Full Table View": "ui.viewsst.full_table_view",
}

# -------------------------------------------------
# Sidebar navigation
# -------------------------------------------------
st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Go to",
    list(PAGES.keys()),
)

# -------------------------------------------------
# Routing (lazy import + render)
# -------------------------------------------------
module_path = PAGES[page]
module = __import__(module_path, fromlist=["render"])
module.render(df_prepared)

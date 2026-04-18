import streamlit as st

# Eager import: router loads screens lazily, so ``ui.screens.board`` may not run on a given
# rerun. Streamlit can still unpickle ``@st.cache_data`` (or related state) that references
# callables under ``services.board_service`` → ``sys.modules['services.board_service']`` must exist.
import services.board_service  # noqa: F401

from ui.components.sidebar import render_sidebar
from ui.data.backend import bootstrap_backend
from ui.router import route_page
from ui.state.session import init_session_state


def main() -> None:
    st.set_page_config(page_title="DMRB", layout="wide")
    init_session_state()
    bootstrap_backend()
    render_sidebar()
    route_page()


if __name__ == "__main__":
    main()

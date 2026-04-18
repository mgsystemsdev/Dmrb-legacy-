"""DMRB AI Agent screen — conversational assistant.

Two-column layout: left sidebar (New Chat + session list),
right panel (suggestion cards or chat messages + input).

Uses OpenAI Chat Completions via `services/ai_agent_chat_service.py`.
Long-term target: FastAPI + worker per blueprint; Legacy calls OpenAI here for local testing.
"""

from __future__ import annotations

import streamlit as st

from config.settings import OPENAI_API_KEY
from services.ai.ai_agent_chat_service import (
    AiAgentApiError,
    AiAgentConfigError,
    complete_chat,
)
from services.ai.ai_agent_context import build_context

_SUGGESTIONS = [
    "Give me the morning briefing",
    "Which units are at highest risk right now?",
    "What should I verify before trusting today's import?",
    "Which units have stalled work?",
]


def _api_key_configured() -> bool:
    return bool((OPENAI_API_KEY or "").strip())


def _load_app_context() -> str | None:
    """Build board snapshot for the active property. Returns None on failure."""
    property_id = st.session_state.get("property_id")
    if property_id is None:
        return None
    try:
        return build_context(property_id)
    except Exception:
        st.error("Could not load board context. Answering without live data.")
        return None


def render_ai_agent() -> None:
    st.subheader("DMRB AI Agent")
    st.caption("AI can make mistakes. Check important info.")

    if not _api_key_configured():
        st.warning(
            "**OPENAI_API_KEY** is not set. Add it to your environment or "
            "`.streamlit/secrets.toml`. See `docs/legacy/AI_AGENT_OPENAI.md`."
        )

    if "ai_session_id" not in st.session_state:
        st.session_state.ai_session_id = None
    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = []
    if "ai_sessions" not in st.session_state:
        st.session_state.ai_sessions = [
            {"session_id": "s1", "title": "Morning briefing"},
            {"session_id": "s2", "title": "Vacant units"},
        ]

    sessions: list[dict] = st.session_state.ai_sessions

    left, right = st.columns([1, 3], gap="small")

    # ── Left: New Chat + Sessions ────────────────────────────────────────
    with left:
        if st.button("+ New Chat", width="stretch", key="ai_new_chat"):
            st.session_state.ai_session_id = None
            st.session_state.ai_messages = []
            st.rerun()

        st.markdown("#### Sessions")
        if not sessions:
            st.caption("No chat sessions yet.")

        for session in sessions:
            sid = session["session_id"]
            title = (session.get("title") or "New Chat")[:40]
            selected = st.session_state.ai_session_id == sid

            row_a, row_b = st.columns([4, 1], gap="small")
            with row_a:
                if st.button(
                    f"{'● ' if selected else ''}{title}",
                    key=f"ai_open_{sid}",
                    width="stretch",
                ):
                    st.session_state.ai_session_id = sid
                    st.session_state.ai_messages = []
                    st.rerun()
            with row_b:
                if st.button("🗑", key=f"ai_del_{sid}", width="stretch"):
                    st.session_state.ai_sessions = [
                        s for s in sessions if s["session_id"] != sid
                    ]
                    if st.session_state.ai_session_id == sid:
                        st.session_state.ai_session_id = None
                        st.session_state.ai_messages = []
                    st.rerun()

    # ── Right: suggestions or messages + chat input ──────────────────────
    with right:
        messages: list[dict] = st.session_state.ai_messages

        if not messages:
            st.markdown("### DMRB AI Agent")
            cols = st.columns(2)
            for idx, question in enumerate(_SUGGESTIONS):
                if cols[idx % 2].button(
                    question,
                    key=f"ai_suggest_{idx}",
                    width="stretch",
                ):
                    new_msgs = [{"role": "user", "content": question}]
                    try:
                        with st.spinner("Thinking…"):
                            app_context = _load_app_context()
                            reply = complete_chat(new_msgs, app_context=app_context)
                    except AiAgentConfigError as e:
                        st.error(str(e))
                    except AiAgentApiError as e:
                        st.error(str(e))
                    else:
                        st.session_state.ai_messages = new_msgs + [
                            {"role": "assistant", "content": reply}
                        ]
                        st.rerun()

        for msg in messages:
            with st.chat_message(msg.get("role", "user")):
                st.markdown(msg.get("content", ""))

        prompt = st.chat_input("Ask anything about turnovers...")
        if prompt:
            new_msgs = list(messages) + [{"role": "user", "content": prompt}]
            try:
                with st.spinner("Thinking…"):
                    app_context = _load_app_context()
                    reply = complete_chat(new_msgs, app_context=app_context)
            except AiAgentConfigError as e:
                st.error(str(e))
            except AiAgentApiError as e:
                st.error(str(e))
            else:
                st.session_state.ai_messages = new_msgs + [
                    {"role": "assistant", "content": reply}
                ]
                st.rerun()

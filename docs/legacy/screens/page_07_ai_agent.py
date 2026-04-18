"""
Page 7 — DMRB AI Agent (skeleton).
Layout-only: two-column chat — left: New Chat, Sessions list; right: suggestions or messages, chat input.
Placeholder data only; no API. Run standalone: streamlit run docs/skeleton_pages/page_07_ai_agent.py
"""
from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Placeholder sessions and suggestions (no API)
# ---------------------------------------------------------------------------
def _placeholder_sessions():
    """List of dicts: session_id, title. Empty → 'No chat sessions yet.'"""
    return [
        {"session_id": "s1", "title": "Morning briefing"},
        {"session_id": "s2", "title": "Vacant units"},
    ]


SUGGESTIONS = [
    "How many units are vacant right now?",
    "Which units are about to breach SLA?",
    "Who has the most open units?",
    "Give me a morning briefing",
]


def render() -> None:
    st.subheader("DMRB AI Agent")
    st.caption("AI can make mistakes. Check important info.")

    if "sk_ai_session_id" not in st.session_state:
        st.session_state.sk_ai_session_id = None
    if "sk_ai_messages" not in st.session_state:
        st.session_state.sk_ai_messages = []

    sessions = _placeholder_sessions()

    left, right = st.columns([1, 3], gap="small")

    # ---------- Left: New Chat + Sessions ----------
    with left:
        if st.button("+ New Chat", use_container_width=True, key="sk_ai_new_chat"):
            st.session_state.sk_ai_session_id = None
            st.session_state.sk_ai_messages = []
            st.rerun()
        st.markdown("#### Sessions")
        if not sessions:
            st.caption("No chat sessions yet.")
        for session in sessions:
            sid = session.get("session_id", "")
            title = (session.get("title") or "New Chat")[:40]
            selected = st.session_state.sk_ai_session_id == sid
            row_a, row_b = st.columns([4, 1], gap="small")
            with row_a:
                if st.button(
                    f"{'● ' if selected else ''}{title}",
                    key=f"sk_ai_open_{sid}",
                    use_container_width=True,
                ):
                    st.session_state.sk_ai_session_id = sid
                    # Placeholder: load fake messages for this session
                    st.session_state.sk_ai_messages = [
                        {"role": "user", "content": "How many units are vacant?"},
                        {"role": "assistant", "content": "There are 12 vacant units."},
                    ]
                    st.rerun()
            with row_b:
                if st.button("🗑", key=f"sk_ai_del_{sid}", use_container_width=True):
                    if st.session_state.sk_ai_session_id == sid:
                        st.session_state.sk_ai_session_id = None
                        st.session_state.sk_ai_messages = []
                    st.rerun()

    # ---------- Right: suggestions or messages + chat input ----------
    with right:
        messages = st.session_state.sk_ai_messages

        if not messages:
            st.markdown("### DMRB AI Agent")
            cols = st.columns(2)
            for idx, question in enumerate(SUGGESTIONS[:6]):
                if cols[idx % 2].button(
                    question,
                    key=f"sk_ai_suggest_{idx}",
                    use_container_width=True,
                ):
                    st.session_state.sk_ai_messages = [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": "(Skeleton: no API — placeholder reply.)"},
                    ]
                    st.rerun()

        for msg in messages:
            role = msg.get("role", "user")
            with st.chat_message(role):
                st.markdown(msg.get("content", ""))

        prompt = st.chat_input("Ask anything about turnovers...")
        if prompt:
            # Skeleton: append user + placeholder assistant reply
            st.session_state.sk_ai_messages = list(messages) + [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": "(Skeleton: no API — your message was received.)"},
            ]
            st.rerun()


if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="DMRB AI Agent (skeleton)")
    render()

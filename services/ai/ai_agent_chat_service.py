"""OpenAI Chat Completions for the Legacy DMRB AI Agent screen.

No Streamlit imports. Long-term target: enqueue via FastAPI + worker (blueprint);
this module is for local Legacy testing only.
"""

from __future__ import annotations

from typing import Any

from openai import APIError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError

from config.settings import OPENAI_API_KEY, OPENAI_CHAT_MODEL

_SYSTEM_PROMPT = """You are DMRB's operational co-manager (Digital Make Ready Board — apartment turnover workflows).
Your role: prioritize data integrity, risk, and failure prevention for the property team.
Predictions and counts must come from the injected board context — do not invent unit numbers, tenant names, or figures not present in context.
If context is absent or a figure is missing, say so and direct the user to check the Board, Unit Detail, or Import Reports screens in the app.
Be concise; use short bullet lists when enumerating items.
You are not legal or financial advice."""


class AiAgentConfigError(Exception):
    """Missing or invalid configuration (e.g. API key)."""


class AiAgentApiError(Exception):
    """OpenAI or network failure surfaced to the user."""


def _normalize_history(history: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in history:
        role = m.get("role")
        content = m.get("content")
        if role not in ("user", "assistant"):
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        out.append({"role": role, "content": content.strip()})
    return out


def complete_chat(
    user_assistant_messages: list[dict[str, Any]],
    app_context: str | None = None,
) -> str:
    """Run one completion turn. `user_assistant_messages` must end with a user message.

    When `app_context` is provided, it is injected as a user-role message before the
    conversation history so the model answers from live board data.
    Returns assistant text.
    """
    key = (OPENAI_API_KEY or "").strip()
    if not key:
        raise AiAgentConfigError(
            "OPENAI_API_KEY is not set. Add it to your environment or "
            "dmrb-legacy/.streamlit/secrets.toml (see docs/legacy/AI_AGENT_OPENAI.md)."
        )

    normalized = _normalize_history(user_assistant_messages)
    if not normalized or normalized[-1]["role"] != "user":
        raise AiAgentApiError("Invalid message history: last message must be from the user.")

    model = (OPENAI_CHAT_MODEL or "gpt-4o-mini").strip()
    messages: list[dict[str, str]] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    if app_context and app_context.strip():
        messages.append(
            {"role": "user", "content": f"Authoritative DMRB context (as of today):\n\n{app_context}"}
        )
    messages.extend(normalized)

    client = OpenAI(api_key=key)
    try:
        resp = client.chat.completions.create(model=model, messages=messages)
    except AuthenticationError as e:
        raise AiAgentApiError("OpenAI authentication failed. Check OPENAI_API_KEY.") from e
    except RateLimitError as e:
        raise AiAgentApiError("OpenAI rate limit reached. Try again shortly.") from e
    except APITimeoutError as e:
        raise AiAgentApiError("OpenAI request timed out. Try again.") from e
    except APIError as e:
        raise AiAgentApiError(f"OpenAI error: {getattr(e, 'message', str(e))}") from e
    except Exception as e:
        raise AiAgentApiError(f"Unexpected error calling OpenAI: {e}") from e

    choice = resp.choices[0].message
    text = (choice.content or "").strip()
    return text if text else "(No response text from the model.)"

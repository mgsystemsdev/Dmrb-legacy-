"""
Chat engine — orchestrates prompt assembly, API calls, and post-response learning.
"""

import pandas as pd
import numpy as np
from datetime import date

from chat.memory import save_message, new_session_id
from chat.context import (
    build_operational_summary,
    build_data_csv,
    build_trend_summary,
    compute_daily_stats,
    store_daily_snapshot,
)
from chat.profile import extract_and_store_insights, build_memory_context, record_workflow_from_exchange


def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize data before context building."""
    df = df.replace("#NUM!", np.nan)

    if "Days_To_MoveIn" in df.columns:
        df["Days_To_MoveIn"] = pd.to_numeric(df["Days_To_MoveIn"], errors="coerce")
    if "W_D" in df.columns:
        df["W_D"] = df["W_D"].fillna("No").replace({"None": "No", "none": "No", "": "No"})
    if "Assign" in df.columns:
        df["Assign"] = df["Assign"].str.strip()

    return df


def build_system_prompt(df: pd.DataFrame, domain_prompt: str) -> str:
    """
    Assemble the full system prompt from all context sources:
    1. Domain knowledge (static rules)
    2. Memory context (learned preferences + session history)
    3. Trend analysis (day-over-day changes)
    4. Operational summary (today's snapshot)
    5. Full data CSV
    """
    today_str = date.today().strftime("%B %d, %Y")

    # Store today's snapshot for future trend analysis
    store_daily_snapshot(df)

    # Build all context sections
    memory_ctx = build_memory_context()
    trend_ctx = build_trend_summary()
    ops_summary = build_operational_summary(df)
    data_csv = build_data_csv(df)

    sections = [
        domain_prompt.format(today=today_str),
        memory_ctx,
        trend_ctx,
        ops_summary,
        f"\n## LIVE DATA (CSV)\n\n{data_csv}",
    ]

    return "\n".join(s for s in sections if s)


def chat(
    user_input: str,
    messages: list[dict],
    api_key: str,
    model: str,
    system_prompt: str,
    session_id: str,
) -> str:
    """
    Execute a full chat cycle:
    1. Call OpenAI with full context
    2. Save messages to SQLite
    3. Extract insights in background
    4. Return the assistant response
    """
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    # Build API messages (cap to last 10 exchanges to bound context and cost)
    max_prior = 20
    prior = messages[:-1][-max_prior:] if len(messages) > 1 else []
    api_messages = [{"role": "system", "content": system_prompt}]
    for msg in prior:
        api_messages.append({"role": msg["role"], "content": msg["content"]})
    api_messages.append({"role": "user", "content": messages[-1]["content"]})

    # Call OpenAI
    response = client.chat.completions.create(
        model=model,
        messages=api_messages,
        temperature=0.2,
    )

    reply = response.choices[0].message.content

    # Persist to SQLite
    save_message(session_id, "user", user_input, model)
    save_message(session_id, "assistant", reply, model)

    # Workflow learning: classify query, record signal, infer first_check / preferences (no LLM)
    record_workflow_from_exchange(
        session_id=session_id,
        user_message=user_input,
        assistant_message=reply,
    )

    # Background learning — only when exchange is substantive (saves extra mini call)
    if len(user_input.strip()) > 15 and len(reply.strip()) > 80:
        extract_and_store_insights(
            user_message=user_input,
            assistant_message=reply,
            session_id=session_id,
            api_key=api_key,
        )

    return reply

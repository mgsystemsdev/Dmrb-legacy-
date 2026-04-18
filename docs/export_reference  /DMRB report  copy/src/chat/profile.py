"""
User profile & preference extraction + workflow learning.

- Insights: LLM-based extraction of preferences/decisions (stored in insights table).
- Workflow: Rule-based query classification + workflow_patterns / user_preferences
  (no conversation history needed; meaningful signals only).
"""

import re
from chat.memory import (
    save_insight,
    get_active_insights,
    get_recent_sessions,
    save_query_signal,
    upsert_workflow_pattern,
    upsert_user_preference,
    get_workflow_patterns,
    get_user_preferences,
    get_query_signal_count_for_session,
)


EXTRACTION_PROMPT = """Analyze this user message from an apartment turnover operations manager.
Extract ONLY concrete, reusable insights. Return a JSON array of objects.

Categories:
- "preference": how they like information formatted or presented
- "decision": a specific operational decision they made
- "priority": what they focus on or care about most
- "style": communication style preferences

Rules:
- Only extract if there's a CLEAR signal. Do not invent.
- Each insight should be a short, specific sentence.
- Return [] if nothing extractable.

Example output:
[
  {"category": "preference", "content": "Prefers tabular format for multi-unit listings"},
  {"category": "priority", "content": "Checks stalled units first thing in the morning"}
]

User message:
{user_message}

Assistant response:
{assistant_message}

Return ONLY the JSON array, no other text."""


def extract_and_store_insights(
    user_message: str,
    assistant_message: str,
    session_id: str,
    api_key: str,
    model: str = "gpt-4o-mini",
):
    """
    Run a lightweight LLM call to extract user preferences/patterns,
    then store them in the insights table.

    Uses gpt-4o-mini for cost efficiency — this is a background extraction,
    not a user-facing response.
    """
    try:
        from openai import OpenAI
        import json

        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": EXTRACTION_PROMPT.format(
                    user_message=user_message,
                    assistant_message=assistant_message[:500],
                ),
            }],
            temperature=0,
            max_tokens=300,
        )

        raw = response.choices[0].message.content.strip()

        # Parse JSON — handle markdown code fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

        insights = json.loads(raw)

        for item in insights:
            if isinstance(item, dict) and "category" in item and "content" in item:
                save_insight(
                    category=item["category"],
                    content=item["content"],
                    source_session=session_id,
                )

    except Exception:
        # Silent fail — preference extraction is best-effort
        pass


# --------------------------------------------------
# Workflow learning: query classification (rule-based, no LLM)
# --------------------------------------------------

# Unit ID pattern: P-B-U e.g. 5-18-0116
UNIT_ID_PATTERN = re.compile(r"\b\d{1,2}-\d{1,2}-\d{3,4}\b")

QUERY_TYPE_KEYWORDS = {
    "single_unit": ["tell me about", "info on", "info for", "lookup", "unit ", "details for", "status of unit", "what about unit"],
    "list_by_priority": ["what should i focus", "focus on", "priorities", "priority list", "what's urgent", "at risk", "critical", "what needs attention", "focus today"],
    "workload": ["workload", "assignee", "miguel", "michael", "brad", "total", "who has", "by person", "by assignee", "each person"],
    "trend": ["trend", "compare", "yesterday", "last week", "change over", "improved", "worsened"],
    "count": ["how many", "count of", "number of", "total vacant", "total ready", "how many units"],
}

def classify_user_query(user_message: str) -> tuple[str, str | None]:
    """
    Classify the user's query type from the message (no conversation history).
    Returns (query_type, hint). hint is optional (e.g. 'stalled', 'move-in risk').
    """
    msg = (user_message or "").strip().lower()
    if not msg:
        return "other", None

    # Single unit: explicit unit ID or "tell me about X"
    if UNIT_ID_PATTERN.search(user_message):
        return "single_unit", None
    for phrase in QUERY_TYPE_KEYWORDS["single_unit"]:
        if phrase in msg:
            return "single_unit", None

    for qtype, phrases in QUERY_TYPE_KEYWORDS.items():
        if qtype == "single_unit":
            continue
        for phrase in phrases:
            if phrase in msg:
                hint = None
                if "stall" in msg or "stalled" in msg:
                    hint = "stalled"
                elif "move-in" in msg or "move in" in msg:
                    hint = "move-in risk"
                elif "breach" in msg:
                    hint = "breach"
                return qtype, hint

    return "other", None


def record_workflow_from_exchange(
    session_id: str,
    user_message: str,
    assistant_message: str,
):
    """
    Record workflow signals from this exchange (no LLM).
    - Classify query -> save to query_signals.
    - If first query in session -> reinforce workflow_pattern first_check.
    - Optionally infer table columns from assistant reply (markdown table header).
    """
    query_type, hint = classify_user_query(user_message)
    count_before = get_query_signal_count_for_session(session_id)

    save_query_signal(session_id, query_type, hint)

    # First query in session = strong signal for "how user starts"
    if count_before == 0:
        first_check_descriptions = {
            "single_unit": "Single unit lookup (specific unit status)",
            "list_by_priority": "Priority list (what to focus on / urgent units)",
            "workload": "Workload by assignee (Miguel G, Michael, Brad, Total)",
            "trend": "Trend or comparison (vs yesterday / last week)",
            "count": "Count or summary (how many units in a state)",
            "other": "General question or open-ended",
        }
        value = first_check_descriptions.get(query_type, first_check_descriptions["other"])
        upsert_workflow_pattern("first_check", "typical_first", value, confidence=0.6, source="inferred_from_queries")

    # Infer table columns from assistant reply (first markdown table header line)
    if query_type == "list_by_priority" and "|" in assistant_message:
        lines = assistant_message.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("|") and line.endswith("|") and "Unit" in line:
                # Normalize: remove outer pipes, split by pipe, strip
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 3:
                    upsert_user_preference("table_columns_list", ", ".join(parts), confidence=0.5)
                break
    elif query_type == "single_unit" and assistant_message:
        # Prefer including these for single-unit (we don't parse reply; set a default once we have data)
        pass


def build_workflow_context() -> str:
    """
    Build "How This User Works" from workflow_patterns and user_preferences.
    Injected into system prompt so the agent applies it without conversation history.
    """
    lines = []
    patterns = get_workflow_patterns()
    prefs = get_user_preferences()

    if not patterns and not prefs:
        return ""

    lines.append("## How This User Works\n")

    if patterns:
        by_type = {}
        for p in patterns:
            by_type.setdefault(p["pattern_type"], []).append(p)
        if "first_check" in by_type:
            for p in by_type["first_check"]:
                lines.append(f"- **Typical first question:** {p['value']}")
        for ptype, items in by_type.items():
            if ptype == "first_check":
                continue
            for p in items:
                lines.append(f"- **{ptype} ({p['key']}):** {p['value']}")

    if prefs:
        lines.append("\n**Stored preferences:**")
        for p in prefs:
            lines.append(f"  - {p['preference_key']}: {p['preference_value']}")

    return "\n".join(lines) + "\n\n" if lines else ""


def build_memory_context() -> str:
    """
    Build the memory/profile section to inject into the system prompt.
    Includes: workflow (how this user works), learned insights, recent session summaries.
    """
    lines = []

    # --- Workflow: how this user works (from workflow_patterns + user_preferences) ---
    workflow_ctx = build_workflow_context()
    if workflow_ctx.strip():
        lines.append(workflow_ctx.strip())
        lines.append("")

    # --- User preferences (legacy free-text insights) ---
    insights = get_active_insights()
    if insights:
        lines.append("## Your Memory — What You've Learned About This User\n")

        by_category = {}
        for ins in insights:
            cat = ins["category"]
            by_category.setdefault(cat, []).append(ins["content"])

        category_labels = {
            "preference": "📋 Format & Presentation Preferences",
            "priority": "🎯 Operational Priorities",
            "decision": "✅ Past Decisions",
            "style": "💬 Communication Style",
        }

        for cat, label in category_labels.items():
            items = by_category.get(cat, [])
            if items:
                # Deduplicate and limit
                unique = list(dict.fromkeys(items))[:8]
                lines.append(f"**{label}:**")
                for item in unique:
                    lines.append(f"  - {item}")
                lines.append("")

    # --- Recent sessions ---
    sessions = get_recent_sessions(n=5)
    if sessions:
        lines.append("**📝 Recent Conversation History:**")
        for sess in sessions:
            topics = sess.get("user_topics", "") or ""
            # Truncate topic summary
            if len(topics) > 150:
                topics = topics[:150] + "..."
            started = sess.get("started", "?")
            msg_count = sess.get("message_count", 0)
            lines.append(f"  - {started} ({msg_count} msgs): {topics}")
        lines.append("")

    return "\n".join(lines)

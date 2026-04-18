"""
SQLite memory layer for Ops Assistant.

Tables:
  - conversations:       every message exchanged (user + assistant)
  - insights:           learned preferences, decisions, patterns (legacy/free-text)
  - daily_snapshots:    operational metrics per day for trend analysis
  - workflow_patterns:  how the user works (first_check, priority_order, etc.)
  - user_preferences:   stable key/value preferences (table columns, fields)
  - query_signals:      query type per turn (no content) for inferring workflow
"""

import sqlite3
import json
import uuid
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "ops_memory.db"


def _connect():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            role        TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            model       TEXT,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS insights (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            category        TEXT    NOT NULL,
            content         TEXT    NOT NULL,
            confidence      REAL    DEFAULT 0.8,
            source_session  TEXT,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            active          BOOLEAN DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS daily_snapshots (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date DATE    UNIQUE NOT NULL,
            total_units   INTEGER,
            vacant_count  INTEGER,
            ready_count   INTEGER,
            stalled_count INTEGER,
            breach_count  INTEGER,
            avg_aging     REAL,
            summary_json  TEXT,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS workflow_patterns (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type  TEXT    NOT NULL,
            key           TEXT    NOT NULL,
            value         TEXT    NOT NULL,
            confidence    REAL    DEFAULT 0.5,
            source        TEXT    DEFAULT 'inferred_from_queries',
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pattern_type, key)
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            preference_key   TEXT    NOT NULL UNIQUE,
            preference_value TEXT    NOT NULL,
            confidence       REAL    DEFAULT 0.5,
            created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS query_signals (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT    NOT NULL,
            query_type TEXT    NOT NULL,
            hint       TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_query_signals_session ON query_signals(session_id);
        CREATE INDEX IF NOT EXISTS idx_query_signals_created ON query_signals(created_at);
    """)
    conn.commit()
    conn.close()


# --------------------------------------------------
# Sessions
# --------------------------------------------------

def new_session_id() -> str:
    return f"S-{uuid.uuid4().hex[:12]}"


# --------------------------------------------------
# Conversations
# --------------------------------------------------

def save_message(session_id: str, role: str, content: str, model: str = None):
    conn = _connect()
    conn.execute(
        "INSERT INTO conversations (session_id, role, content, model) VALUES (?, ?, ?, ?)",
        (session_id, role, content, model),
    )
    conn.commit()
    conn.close()


def get_session_messages(session_id: str) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT role, content, timestamp FROM conversations WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_sessions(n: int = 5) -> list[dict]:
    """Get summaries of the last N distinct sessions."""
    conn = _connect()
    rows = conn.execute("""
        SELECT session_id,
               MIN(timestamp) as started,
               MAX(timestamp) as ended,
               COUNT(*) as message_count,
               GROUP_CONCAT(
                   CASE WHEN role = 'user' THEN content ELSE NULL END,
                   ' | '
               ) as user_topics
        FROM conversations
        GROUP BY session_id
        ORDER BY MAX(timestamp) DESC
        LIMIT ?
    """, (n,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_total_conversation_count() -> int:
    conn = _connect()
    count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    conn.close()
    return count


# --------------------------------------------------
# Insights (preferences, decisions, patterns)
# --------------------------------------------------

def save_insight(category: str, content: str, source_session: str = None, confidence: float = 0.8):
    conn = _connect()
    conn.execute(
        "INSERT INTO insights (category, content, source_session, confidence) VALUES (?, ?, ?, ?)",
        (category, content, source_session, confidence),
    )
    conn.commit()
    conn.close()


def get_active_insights() -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT category, content, confidence, created_at FROM insights WHERE active = 1 ORDER BY created_at DESC",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def deactivate_insight(insight_id: int):
    conn = _connect()
    conn.execute("UPDATE insights SET active = 0 WHERE id = ?", (insight_id,))
    conn.commit()
    conn.close()


# --------------------------------------------------
# Daily Snapshots (for trend analysis)
# --------------------------------------------------

def save_daily_snapshot(stats: dict):
    today = date.today().isoformat()
    conn = _connect()
    conn.execute("""
        INSERT OR REPLACE INTO daily_snapshots
            (snapshot_date, total_units, vacant_count, ready_count,
             stalled_count, breach_count, avg_aging, summary_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        today,
        stats.get("total_units", 0),
        stats.get("vacant_count", 0),
        stats.get("ready_count", 0),
        stats.get("stalled_count", 0),
        stats.get("breach_count", 0),
        stats.get("avg_aging", 0),
        json.dumps(stats),
    ))
    conn.commit()
    conn.close()


def get_snapshot_history(days: int = 30) -> list[dict]:
    conn = _connect()
    rows = conn.execute("""
        SELECT snapshot_date, total_units, vacant_count, ready_count,
               stalled_count, breach_count, avg_aging, summary_json
        FROM daily_snapshots
        ORDER BY snapshot_date DESC
        LIMIT ?
    """, (days,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --------------------------------------------------
# Workflow patterns (how the user works)
# --------------------------------------------------

def save_query_signal(session_id: str, query_type: str, hint: str = None):
    conn = _connect()
    conn.execute(
        "INSERT INTO query_signals (session_id, query_type, hint) VALUES (?, ?, ?)",
        (session_id, query_type, hint),
    )
    conn.commit()
    conn.close()


def upsert_workflow_pattern(pattern_type: str, key: str, value: str, confidence: float = 0.5, source: str = "inferred_from_queries"):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    conn.execute("""
        INSERT INTO workflow_patterns (pattern_type, key, value, confidence, source, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(pattern_type, key) DO UPDATE SET
            value = excluded.value,
            confidence = MIN(1.0, workflow_patterns.confidence + 0.1),
            source = excluded.source,
            updated_at = excluded.updated_at
    """, (pattern_type, key, value, confidence, source, now))
    conn.commit()
    conn.close()


def get_workflow_patterns() -> list[dict]:
    conn = _connect()
    rows = conn.execute("""
        SELECT pattern_type, key, value, confidence
        FROM workflow_patterns
        ORDER BY pattern_type, key
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --------------------------------------------------
# User preferences (stable key/value)
# --------------------------------------------------

def upsert_user_preference(preference_key: str, preference_value: str, confidence: float = 0.5):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    conn.execute("""
        INSERT INTO user_preferences (preference_key, preference_value, confidence, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(preference_key) DO UPDATE SET
            preference_value = excluded.preference_value,
            confidence = MIN(1.0, user_preferences.confidence + 0.05),
            updated_at = excluded.updated_at
    """, (preference_key, preference_value, confidence, now))
    conn.commit()
    conn.close()


def get_user_preferences() -> list[dict]:
    conn = _connect()
    rows = conn.execute("""
        SELECT preference_key, preference_value, confidence
        FROM user_preferences
        ORDER BY preference_key
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_last_query_signal_for_session(session_id: str) -> dict | None:
    """Used to detect 'first query in session' for workflow inference."""
    conn = _connect()
    row = conn.execute(
        "SELECT query_type, hint FROM query_signals WHERE session_id = ? ORDER BY id DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_query_signal_count_for_session(session_id: str) -> int:
    conn = _connect()
    count = conn.execute("SELECT COUNT(*) FROM query_signals WHERE session_id = ?", (session_id,)).fetchone()[0]
    conn.close()
    return count


# Initialize on import
init_db()

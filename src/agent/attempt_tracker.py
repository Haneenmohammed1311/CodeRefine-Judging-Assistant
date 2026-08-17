"""
Tracks how many times each team has submitted, so the system can decide
automatically which behavior applies, no separate practice or official
button for a team to choose between.

Attempts 1 and 2: automatic feedback, no score, no judge involved.
Attempt 3: the real, judge reviewed grading run.
Attempt 4 and beyond: refused, a team gets exactly three tries.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("logs/attempts.db")
MAX_ATTEMPTS = 3
FINAL_ATTEMPT_NUMBER = 3


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            team_name TEXT PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0
        )
    """)
    return conn


def get_attempt_count(team_name: str) -> int:
    conn = _get_connection()
    try:
        row = conn.execute("SELECT count FROM attempts WHERE team_name = ?", (team_name,)).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def record_attempt(team_name: str) -> int:
    """Increments and returns the new attempt count. Call this once the attempt actually starts running."""
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO attempts (team_name, count) VALUES (?, 1) "
            "ON CONFLICT(team_name) DO UPDATE SET count = count + 1",
            (team_name,),
        )
        conn.commit()
        return get_attempt_count(team_name)
    finally:
        conn.close()


class NoAttemptsRemainingError(Exception):
    """Raised when a team tries to submit a fourth time. Three attempts is the limit, by design."""

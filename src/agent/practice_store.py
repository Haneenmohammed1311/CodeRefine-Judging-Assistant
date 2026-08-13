"""
Stores practice-trial feedback so a team can check back for it after
submitting separate from review_queue.py on purpose, since practice
trials never need approve/release/status-machine logic at all, just
"is it done yet, and what did it say." Same SQLite approach as the
review queue, for the same reason: safe under concurrent access.
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path("logs/practice_feedback.db")


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS practice_feedback (
            team_name TEXT PRIMARY KEY,
            repo_url TEXT NOT NULL,
            feedback TEXT,
            status TEXT NOT NULL
        )
    """)
    return conn


def start_practice(team_name: str, repo_url: str) -> None:
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO practice_feedback (team_name, repo_url, feedback, status) VALUES (?, ?, NULL, 'pending')",
            (team_name, repo_url),
        )
        conn.commit()
    finally:
        conn.close()


def complete_practice(team_name: str, feedback: list) -> None:
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE practice_feedback SET feedback = ?, status = 'done' WHERE team_name = ?",
            (json.dumps(feedback), team_name),
        )
        conn.commit()
    finally:
        conn.close()


def get_practice(team_name: str) -> dict | None:
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT repo_url, feedback, status FROM practice_feedback WHERE team_name = ?",
            (team_name,),
        ).fetchone()
        if row is None:
            return None
        repo_url, feedback_json, status = row
        return {
            "team_name": team_name,
            "repo_url": repo_url,
            "feedback": json.loads(feedback_json) if feedback_json else None,
            "status": status,
        }
    finally:
        conn.close()

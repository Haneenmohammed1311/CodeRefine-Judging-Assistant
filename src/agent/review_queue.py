"""
The review queue tracks the CURRENT status of each team's grading result:
pending review, approved, or released to the team.

This is deliberately separate from logging_utils.py's scorecards.jsonl:
- scorecards.jsonl: an immutable, append-only history of every grading run
  ever performed (for dispute resolution, never edited).
- review_queue.db: the current, editable state of each team's submission
  (one row per team, updated as it moves through the workflow).

Uses SQLite instead of a single JSON file specifically for concurrency
safety: judges can act through the API at the same moment
(two near-simultaneous approvals could silently overwrite each other).
SQLite handles concurrent writes correctly on its own, with no extra
library needed (it's part of Python's standard library) and no separate
database server to run.

"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("logs/review_queue.db")


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    # timeout=10 -- if the database is briefly locked by another judge's
    # write happening at the same moment, wait up to 10 seconds and retry
    # automatically, instead of failing immediately.
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            team_name TEXT PRIMARY KEY,
            repo_url TEXT NOT NULL,
            scorecard TEXT NOT NULL,
            verification_notes TEXT,
            status TEXT NOT NULL,
            judge_notes TEXT DEFAULT '',
            graded_at TEXT,
            reviewed_at TEXT
        )
    """)
    return conn


def _row_to_entry(row: tuple) -> dict:
    (team_name, repo_url, scorecard_json, verification_notes,
     status, judge_notes, graded_at, reviewed_at) = row
    return {
        "team_name": team_name,
        "repo_url": repo_url,
        "scorecard": json.loads(scorecard_json),
        "verification_notes": verification_notes,
        "status": status,
        "judge_notes": judge_notes,
        "graded_at": graded_at,
        "reviewed_at": reviewed_at,
    }


def add_pending(team_name: str, repo_url: str, final_scorecard: list, verification_notes: str) -> None:
    """Called right after the agent finishes grading a team -- status starts as 'pending_review'."""
    conn = _get_connection()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO submissions
               (team_name, repo_url, scorecard, verification_notes, status, judge_notes, graded_at, reviewed_at)
               VALUES (?, ?, ?, ?, 'pending_review', '', ?, NULL)""",
            (team_name, repo_url, json.dumps(final_scorecard), verification_notes,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def list_pending() -> list[dict]:
    """What a judge sees when they ask 'who's waiting for my review?'"""
    return list_by_status("pending_review")


def get(team_name: str) -> dict | None:
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT team_name, repo_url, scorecard, verification_notes, status, judge_notes, graded_at, reviewed_at "
            "FROM submissions WHERE team_name = ?",
            (team_name,),
        ).fetchone()
        return _row_to_entry(row) if row else None
    finally:
        conn.close()


def approve(team_name: str, judge_notes: str = "", edited_scorecard: list | None = None) -> dict:
    """
    A judge approves a team's scorecard, moving it to 'approved'. The judge
    can optionally override the agent's scorecard entirely (edited_scorecard)
    -- the agent's output is a draft, the judge always has final say, per
    the competition's own rules that judges' decisions are final.
    """
    conn = _get_connection()
    try:
        existing = conn.execute(
            "SELECT scorecard FROM submissions WHERE team_name = ?", (team_name,)
        ).fetchone()
        if existing is None:
            raise ValueError(f"No pending entry for team '{team_name}'.")

        scorecard_json = json.dumps(edited_scorecard) if edited_scorecard is not None else existing[0]
        conn.execute(
            """UPDATE submissions
               SET scorecard = ?, judge_notes = ?, status = 'approved', reviewed_at = ?
               WHERE team_name = ?""",
            (scorecard_json, judge_notes, datetime.now(timezone.utc).isoformat(), team_name),
        )
        conn.commit()
        return get(team_name)
    finally:
        conn.close()


def release(team_name: str) -> dict:
    """
    Marks a team's result as visible to them. Separate step from 'approve'
    on purpose -- a judge might approve several teams in one sitting, then
    release them all together (e.g. at a scheduled results announcement
    time), rather than each release happening the instant it's approved.
    """
    conn = _get_connection()
    try:
        row = conn.execute("SELECT status FROM submissions WHERE team_name = ?", (team_name,)).fetchone()
        if row is None:
            raise ValueError(f"No entry for team '{team_name}'.")
        if row[0] != "approved":
            raise ValueError(f"Team '{team_name}' must be approved before release (current status: {row[0]}).")

        conn.execute("UPDATE submissions SET status = 'released' WHERE team_name = ?", (team_name,))
        conn.commit()
        return get(team_name)
    finally:
        conn.close()


def list_by_status(status: str) -> list[dict]:
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT team_name, repo_url, scorecard, verification_notes, status, judge_notes, graded_at, reviewed_at "
            "FROM submissions WHERE status = ?",
            (status,),
        ).fetchall()
        return [_row_to_entry(row) for row in rows]
    finally:
        conn.close()

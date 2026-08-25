"""
The review queue tracks the CURRENT status of each team's grading result:
pending review, approved, or released to the team.
 
This is deliberately separate from logging_utils.py's scorecards.jsonl:
- scorecards.jsonl: an immutable, append-only history of every grading run
  ever performed (for dispute resolution never edited).
- review_queue.db: the current, editable state of each team's submission
  (one row per team, updated as it moves through the workflow).
 
Uses SQLite instead of a single JSON file specifically for concurrency
safety: the previous version read the whole file, changed one entry, and
wrote the whole file back fine for one person running commands, but
unsafe once multiple judges can act through the API at the same moment
(two near-simultaneous approvals could silently overwrite each other).
SQLite handles concurrent writes correctly on its own, with no extra
library needed (it's part of Python's standard library) and no separate
database server to run.
 
Every public function keeps the exact same name and signature as the
JSON-file version.
"""


import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
 
DB_PATH = Path("logs/review_queue.db")
 
 
def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    # timeout=10 if the database is briefly locked by another judge's
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
            reviewed_at TEXT,
            bonus_percent INTEGER DEFAULT 0
        )
    """)
    # Migration for databases created before bonus_percent existed
    # SQLite has no "ADD COLUMN IF NOT EXISTS", so check first.
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(submissions)")}
    if "bonus_percent" not in existing_columns:
        conn.execute("ALTER TABLE submissions ADD COLUMN bonus_percent INTEGER DEFAULT 0")
    return conn


def _row_to_entry(row: tuple) -> dict:
    (team_name, repo_url, scorecard_json, verification_notes,
     status, judge_notes, graded_at, reviewed_at, bonus_percent) = row
    return {
        "team_name": team_name,
        "repo_url": repo_url,
        "scorecard": json.loads(scorecard_json),
        "verification_notes": verification_notes,
        "status": status,
        "judge_notes": judge_notes,
        "graded_at": graded_at,
        "reviewed_at": reviewed_at,
        "bonus_percent": bonus_percent,
    }
 
 
class SubmissionCollisionError(Exception):
    """
    Raised when a new grading result would silently overwrite an existing
    one that's already been approved or released. team_name alone is not
    a guaranteed-unique key (real teams have reused the exact same names,
    since some just use the competition's system-design topic as their
    team name) this stops a name collision, or a mistaken re-run, from
    quietly destroying a finalized result.
    """


def add_pending(team_name: str, repo_url: str, final_scorecard: list, verification_notes: str) -> None:
    """Called right after the agent finishes grading a team status starts as 'pending_review'."""
    conn = _get_connection()
    try:
        existing = conn.execute(
            "SELECT repo_url, status FROM submissions WHERE team_name = ?", (team_name,)
        ).fetchone()
 
        if existing is not None:
            existing_repo_url, existing_status = existing
            if existing_status in ("approved", "released"):
                raise SubmissionCollisionError(
                    f"'{team_name}' already has a {existing_status} result "
                    f"(repo: {existing_repo_url}). Refusing to overwrite it. "
                    f"If this is genuinely a different team with the same "
                    f"name, they need a distinguishable identifier -- team "
                    f"names alone aren't guaranteed unique."
                )
            if existing_repo_url != repo_url:
                print(
                    f"WARNING: '{team_name}' was previously submitted with a "
                    f"different repo ({existing_repo_url}), now resubmitting "
                    f"with {repo_url}. Proceeding since the prior result was "
                    f"still pending review, not yet finalized. This may be a "
                    f"legitimate resubmission, or two different teams "
                    f"sharing the same name -- worth a judge double-checking."
                )
 
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

def approve(team_name: str, judge_notes: str = "", edited_scorecard: list | None = None, bonus_percent: int = 0) -> dict:

    """
    A judge approves a team's scorecard, moving it to 'approved'. The judge
    can optionally override the agent's scorecard entirely (edited_scorecard)
    the agent's output is a draft, the judge always has final say, per
    the competition's own rules that judges' decisions are final.
    
    bonus_percent (0-10): the Bonus criterion is deliberately scored ONLY
    by the judge, never by the agent
    """
    if not (0 <= bonus_percent <= 10):
        raise ValueError(f"bonus_percent must be between 0 and 10, got {bonus_percent}.")

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
               SET scorecard = ?, judge_notes = ?, status = 'approved', reviewed_at = ?, bonus_percent = ?
               WHERE team_name = ?""",
            (scorecard_json, judge_notes, datetime.now(timezone.utc).isoformat(), bonus_percent, team_name),
        )
        conn.commit()
        return get(team_name)
    finally:
        conn.close()

def release(team_name: str) -> dict:
    """
    Marks a team's result as visible to them. Separate step from 'approve'
    on purpose a judge might approve several teams in one sitting, then
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
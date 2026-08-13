"""
Append-only logs, as plain JSON-lines files (one JSON object per line --
simple, human-readable, no database needed for this scale):

- logs/scorecards.jsonl -> every OFFICIAL grading result, for dispute
  resolution  only ever written after judge involvement is possible
- logs/practice_feedback.jsonl -> every practice-trial feedback given,
  kept SEPARATE from the official log since practice trials never
  involve a judge and never carry a score  mixing them would make it
  unclear later which entries were real grades and which weren't
- logs/questions.jsonl  -> every question the chatbot answered
"""

import json
from datetime import datetime, timezone
from pathlib import Path

LOGS_DIR = Path("logs")
SCORECARD_LOG = LOGS_DIR / "scorecards.jsonl"
PRACTICE_FEEDBACK_LOG = LOGS_DIR / "practice_feedback.jsonl"
QUESTION_LOG = LOGS_DIR / "questions.jsonl"


def _append_jsonl(path: Path, record: dict) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **record}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def log_scorecard(team_name: str, repo_url: str, final_scorecard: list, verification_notes: str) -> None:
    _append_jsonl(SCORECARD_LOG, {
        "team_name": team_name,
        "repo_url": repo_url,
        "scorecard": final_scorecard,
        "verification_notes": verification_notes,
    })


def log_practice_feedback(team_name: str, repo_url: str, feedback: list) -> None:
    _append_jsonl(PRACTICE_FEEDBACK_LOG, {
        "team_name": team_name,
        "repo_url": repo_url,
        "feedback": feedback,
    })


def log_question(question: str, answer: str) -> None:
    _append_jsonl(QUESTION_LOG, {"question": question, "answer": answer})

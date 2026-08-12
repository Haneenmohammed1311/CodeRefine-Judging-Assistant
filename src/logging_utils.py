"""
Two append-only logs, as plain JSON-lines files (one JSON object per line --
simple, human-readable, no database needed for this scale):

- logs/scorecards.jsonl -> every grading result, for dispute resolution
- logs/questions.jsonl  -> every question the chatbot answered
"""

import json
from datetime import datetime, timezone
from pathlib import Path

LOGS_DIR = Path("logs")
SCORECARD_LOG = LOGS_DIR / "scorecards.jsonl"
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


def log_question(question: str, answer: str) -> None:
    _append_jsonl(QUESTION_LOG, {"question": question, "answer": answer})

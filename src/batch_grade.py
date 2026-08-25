"""

Important: this deliberately calls grade_repo() directly, bypassing the
3-attempt system in src/agent/attempt_tracker.py entirely. This tool is
meant for a final, forced grading pass, after the deadline, grading
everyone's final repo regardless of how many times they used the normal
team-facing submission flow. It does not increment or check a team's
attempt count. If that's not what you want, use the website or the
`submit` CLI command instead, which do respect the attempt system.

Expected CSV format (a header row, then one row per team):
    team_name,repo_url
    Team Alpha,https://github.com/alpha-team/coderefine

Usage:
    poetry run python -m src.batch_grade submissions.csv
"""

import csv
import sys
import time

from dotenv import load_dotenv

load_dotenv()

# Grading one team makes 2 LLM calls (gather + format) that can together
# use 6,000-10,000 tokens close to or over Groq's free-tier 8,000
# tokens/minute limit by itself. This pause is the first line of defense;
# the retry logic below is the second, for when a team's run genuinely
# gets rate-limited anyway.
SECONDS_BETWEEN_TEAMS = 8
MAX_RETRIES_ON_RATE_LIMIT = 3
RETRY_BACKOFF_SECONDS = 30


def _is_rate_limit_error(exception: Exception) -> bool:
    """
    Distinguishes a rate-limit error (worth waiting and retrying) from a
    genuine failure like a bad URL or private repo (retrying won't help,
    move on). Groq's rate-limit errors mention 'rate_limit' or the HTTP
    429/413 status in their message checking the message text rather
    than importing Groq's specific exception classes keeps this file from
    needing to know about Groq internals directly.
    """
    message = str(exception).lower()
    return "rate_limit" in message or "429" in message or "413" in message


def _grade_one_team(team_name: str, repo_url: str) -> None:
    from src.agent.graph import grade_repo
    from src.logging_utils import log_scorecard
    from src.agent.review_queue import add_pending

    result = grade_repo(team_name=team_name, repo_url=repo_url)
    log_scorecard(
        team_name=team_name,
        repo_url=repo_url,
        final_scorecard=result["final_scorecard"],
        verification_notes=result["verification_notes"],
    )
    add_pending(
        team_name=team_name,
        repo_url=repo_url,
        final_scorecard=result["final_scorecard"],
        verification_notes=result["verification_notes"],
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: poetry run python -m src.batch_grade submissions.csv")
        return

    csv_path = sys.argv[1]
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Found {len(rows)} submissions to grade.\n")
    failed_teams = []

    for i, row in enumerate(rows, 1):
        team_name = row["team_name"].strip()
        repo_url = row["repo_url"].strip()
        print(f"[{i}/{len(rows)}] Grading {team_name} ({repo_url})...")

        attempt = 0
        while True:
            attempt += 1
            try:
                _grade_one_team(team_name, repo_url)
                print(f"    Done -- added to review queue.\n")
                break
            except Exception as e:
                if _is_rate_limit_error(e) and attempt <= MAX_RETRIES_ON_RATE_LIMIT:
                    wait = RETRY_BACKOFF_SECONDS * attempt  # back off further each retry
                    print(f"    Rate limited (attempt {attempt}/{MAX_RETRIES_ON_RATE_LIMIT}) -- waiting {wait}s and retrying...")
                    time.sleep(wait)
                    continue
                # Either a genuine failure (wrong URL, private repo, etc.),
                # or we've exhausted retries on a persistent rate limit
                # either way, don't let one team stop the whole batch.
                print(f"    FAILED after {attempt} attempt(s): {e}\n")
                failed_teams.append(team_name)
                break

        if i < len(rows):
            time.sleep(SECONDS_BETWEEN_TEAMS)

    print("Batch complete. Run the review queue to see what's pending.")
    if failed_teams:
        print(f"\n{len(failed_teams)} team(s) failed and need manual attention: {', '.join(failed_teams)}")


if __name__ == "__main__":
    main()

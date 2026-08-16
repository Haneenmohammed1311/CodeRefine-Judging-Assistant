"""
Grades every team in a CSV file, instead of typing one teamrepo pair
at a time. This is the realistic way many teams actually get graded: they
fill out a submission form, you export the responses
to a CSV, and this script processes the whole batch.

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


def main():
    if len(sys.argv) < 2:
        print("Usage: poetry run python -m src.batch_grade submissions.csv")
        return

    from src.agent.graph import grade_repo
    from src.logging_utils import log_scorecard
    from src.agent.review_queue import add_pending

    csv_path = sys.argv[1]
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Found {len(rows)} submissions to grade.\n")

    for i, row in enumerate(rows, 1):
        team_name = row["team_name"].strip()
        repo_url = row["repo_url"].strip()
        print(f"[{i}/{len(rows)}] Grading {team_name} ({repo_url})...")

        try:
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
            print(f"    Done -- added to review queue.\n")
        except Exception as e:
            # One team's failure (bad URL, private repo, etc.) shouldn't
            # stop the whole batch print it and keep going.
            print(f"    FAILED: {e}\n")

        # Small pause between teams to stay under Groq's per-minute token
        # limit (the same limit that caused the 413 error earlier).
        if i < len(rows):
            time.sleep(5)

    print("Batch complete. Run the review queue to see what's pending.")


if __name__ == "__main__":
    main()
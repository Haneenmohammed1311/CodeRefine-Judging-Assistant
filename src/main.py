"""
The single entry point for running this project.

Usage:
    poetry run python -m src.main grade --team "Team Name" --repo https://github.com/owner/repo
    poetry run python -m src.main review
    poetry run python -m src.main approve --team "Team Name" --notes "looks good"
    poetry run python -m src.main release --team "Team Name"
    poetry run python -m src.main report --team "Team Name"
    poetry run python -m src.main chat
"""

import argparse
import json

from dotenv import load_dotenv

load_dotenv()  # reads .env so GROQ_API_KEY / GITHUB_TOKEN are available


def run_practice(team: str, repo: str) -> None:
    from src.agent.graph import give_practice_feedback
    from src.logging_utils import log_practice_feedback

    result = give_practice_feedback(team_name=team, repo_url=repo)

    print(f"Practice feedback for '{team}' -- no score, no judge review:\n")
    for item in result["feedback"]:
        print(f"  {item['criterion']} ({item['confidence']} confidence)")
        print(f"    {item['feedback']}")

    log_practice_feedback(team_name=team, repo_url=repo, feedback=result["feedback"])
    print(f"\nSeen only by '{team}' -- never enters the judge review queue.")


def run_grade(team: str, repo: str) -> None:
    from src.agent.graph import grade_repo
    from src.logging_utils import log_scorecard
    from src.agent.review_queue import add_pending

    result = grade_repo(team_name=team, repo_url=repo)

    print(json.dumps(result["final_scorecard"], indent=2))
    print(f"\nVerification notes: {result['verification_notes']}")

    log_scorecard(
        team_name=team,
        repo_url=repo,
        final_scorecard=result["final_scorecard"],
        verification_notes=result["verification_notes"],
    )
    add_pending(
        team_name=team,
        repo_url=repo,
        final_scorecard=result["final_scorecard"],
        verification_notes=result["verification_notes"],
    )
    print(f"\n'{team}' added to the review queue (status: pending_review).")


def run_review() -> None:
    from src.agent.review_queue import list_pending

    pending = list_pending()
    if not pending:
        print("Nothing pending review.")
        return

    for entry in pending:
        print(f"\n=== {entry['team_name']} ({entry['repo_url']}) ===")
        for item in entry["scorecard"]:
            print(f"  {item['criterion']}: {item.get('score_percent', 0)}% ({item['confidence']} confidence)")
            print(f"    {item['justification']}")
        print(f"  Verification: {entry['verification_notes']}")


def run_approve(team: str, notes: str) -> None:
    from src.agent.review_queue import approve

    entry = approve(team, judge_notes=notes)
    print(f"'{team}' approved. Status: {entry['status']}")


def run_release(team: str) -> None:
    from src.agent.review_queue import release

    entry = release(team)
    print(f"'{team}' released. Status: {entry['status']}")


def run_report(team: str) -> None:
    from src.agent.report import generate_team_report

    print(generate_team_report(team))


def run_chat() -> None:
    import uuid
    from src.chatbot.chatbot import answer_question

    # One thread_id for this whole session every question you type here
    # shares memory with every question before it, until you exit.
    thread_id = str(uuid.uuid4())

    print("Team support chatbot. Type 'exit' to quit.\n")
    while True:
        question = input("Q: ").strip()
        if question.lower() in ("exit", "quit"):
            break
        print(f"A: {answer_question(question, thread_id=thread_id)}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="CodeRefine judging & support system")
    subparsers = parser.add_subparsers(dest="command", required=True)

    grade_parser = subparsers.add_parser("grade", help="Grade one team's repo (official, needs judge approval)")
    grade_parser.add_argument("--team", required=True)
    grade_parser.add_argument("--repo", required=True)

    practice_parser = subparsers.add_parser("practice", help="Give practice feedback (no score, no judge review)")
    practice_parser.add_argument("--team", required=True)
    practice_parser.add_argument("--repo", required=True)

    subparsers.add_parser("review", help="List teams pending judge review")

    approve_parser = subparsers.add_parser("approve", help="Judge approves a team's scorecard")
    approve_parser.add_argument("--team", required=True)
    approve_parser.add_argument("--notes", default="")

    release_parser = subparsers.add_parser("release", help="Release an approved result to the team")
    release_parser.add_argument("--team", required=True)

    report_parser = subparsers.add_parser("report", help="Generate a team-facing report")
    report_parser.add_argument("--team", required=True)

    subparsers.add_parser("chat", help="Start the team support chatbot")

    args = parser.parse_args()

    if args.command == "grade":
        run_grade(args.team, args.repo)
    elif args.command == "practice":
        run_practice(args.team, args.repo)
    elif args.command == "review":
        run_review()
    elif args.command == "approve":
        run_approve(args.team, args.notes)
    elif args.command == "release":
        run_release(args.team)
    elif args.command == "report":
        run_report(args.team)
    elif args.command == "chat":
        run_chat()


if __name__ == "__main__":
    main()

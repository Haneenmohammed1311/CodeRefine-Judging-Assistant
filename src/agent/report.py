"""
Generates the report a TEAM actually sees built from the queue entry,
and only for entries that have been explicitly released. This is the
"here's your grade, here's why, here's how to improve" document.

Kept as a separate function from the scorecard data itself: the internal
scorecard (with confidence levels, raw evidence, judge notes) and the
team-facing report (readable, encouraging, actionable) are different
audiences with different needs, even though they come from the same data.
"""

from src.agent.review_queue import get
from src.agent.rubric import RUBRIC, BONUS_MAX_PERCENT


def generate_team_report(team_name: str) -> str:
    entry = get(team_name)
    if entry is None:
        return f"No grading record found for '{team_name}'."

    if entry["status"] != "released":
        return (
            f"Results for '{team_name}' are not yet available "
            f"(current status: {entry['status']})."
        )

    lines = [f"# CodeRefine Results, {team_name}", ""]

    weight_by_criterion = {r["criterion"]: r["weight_percent"] for r in RUBRIC}
    base_total = sum(item.get("score_percent", 0) for item in entry["scorecard"])
    bonus = entry.get("bonus_percent", 0)
    grand_total = base_total + bonus

    lines.append(f"**Total score:** {grand_total} / 100 ({base_total} base plus {bonus} bonus)\n")

    for item in entry["scorecard"]:
        max_for_this = weight_by_criterion.get(item["criterion"], "?")
        lines.append(f"## {item['criterion']}: {item.get('score_percent', 0)} / {max_for_this}")
        lines.append(f"{item.get('justification', 'No justification recorded.')}")
        if item.get("confidence") == "low":
            lines.append(
                "\n_Note: this criterion had limited supporting evidence during review, "
                "if you believe this score doesn't reflect your submission, please reach "
                "out to the organizers._"
            )
        lines.append("")

    if bonus > 0:
        lines.append(f"## Bonus: {bonus} / {BONUS_MAX_PERCENT}")
        lines.append("Awarded directly by the judge.\n")
    else:
        lines.append(f"_No bonus (up to {BONUS_MAX_PERCENT} points possible) was awarded for this submission._\n")

    if entry.get("judge_notes"):
        lines.append("## Judge's notes")
        lines.append(entry["judge_notes"])
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: poetry run python -m src.agent.report \"Team Name\"")
    else:
        print(generate_team_report(sys.argv[1]))
